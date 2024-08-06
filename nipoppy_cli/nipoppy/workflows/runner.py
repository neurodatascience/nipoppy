"""PipelineRunner workflow."""

import logging
from functools import cached_property
from pathlib import Path
from typing import Optional

from boutiques import bosh

from nipoppy.config.boutiques import BoutiquesConfig
from nipoppy.config.container import ContainerConfig, prepare_container
from nipoppy.env import StrOrPathLike
from nipoppy.tabular.bagel import Bagel
from nipoppy.workflows.pipeline import BasePipelineWorkflow


class PipelineRunner(BasePipelineWorkflow):
    """Pipeline runner."""

    def __init__(
        self,
        dpath_root: StrOrPathLike,
        pipeline_name: str,
        pipeline_version: Optional[str] = None,
        pipeline_step: Optional[str] = None,
        participant_id: str = None,
        session_id: str = None,
        simulate: bool = False,
        fpath_layout: Optional[StrOrPathLike] = None,
        logger: Optional[logging.Logger] = None,
        dry_run: bool = False,
    ):
        super().__init__(
            dpath_root=dpath_root,
            name="run",
            pipeline_name=pipeline_name,
            pipeline_version=pipeline_version,
            pipeline_step=pipeline_step,
            participant_id=participant_id,
            session_id=session_id,
            fpath_layout=fpath_layout,
            logger=logger,
            dry_run=dry_run,
        )
        self.simulate = simulate

    @cached_property
    def dpaths_to_check(self) -> list[Path]:
        """Directory paths to create if needed during the setup phase."""
        return super().dpaths_to_check + [
            self.dpath_pipeline_output,
            self.dpath_pipeline_work,
        ]

    def process_container_config(
        self,
        participant_id: str,
        session_id: str,
        bind_paths: Optional[list[StrOrPathLike]] = None,
    ) -> str:
        """Update container config and generate container command."""
        if bind_paths is None:
            bind_paths = []

        # get and process container config
        container_config = self.pipeline_config.get_container_config()
        container_config = ContainerConfig(
            **self.process_template_json(
                container_config.model_dump(),
                participant_id=participant_id,
                session_id=session_id,
            )
        )
        self.logger.debug(f"Initial container config: {container_config}")

        # get and process Boutiques config
        boutiques_config = BoutiquesConfig(
            **self.process_template_json(
                self.boutiques_config.model_dump(),
                participant_id=participant_id,
                session_id=session_id,
            )
        )

        # update container config with additional information from Boutiques config
        self.logger.debug(f"Boutiques config: {boutiques_config}")
        if boutiques_config != BoutiquesConfig():
            self.logger.info("Updating container config with config from descriptor")
            container_config.merge(boutiques_config.get_container_config())

        # add bind paths
        for bind_path in bind_paths:
            container_config.add_bind_path(bind_path)

        self.logger.info(f"Using container config: {container_config}")

        container_command = prepare_container(
            container_config,
            subcommand=boutiques_config.CONTAINER_SUBCOMMAND,
            check=True,
            logger=self.logger,
        )

        return container_command

    def launch_boutiques_run(
        self,
        participant_id: str,
        session_id: str,
        objs: Optional[list] = None,
        **kwargs,
    ):
        """Launch a pipeline run using Boutiques."""
        # process and validate the descriptor
        self.logger.info("Processing the JSON descriptor")
        descriptor_str = self.process_template_json(
            self.descriptor,
            participant_id=participant_id,
            session_id=session_id,
            objs=objs,
            **kwargs,
            return_str=True,
        )
        self.logger.debug(f"Descriptor string: {descriptor_str}")
        self.logger.info("Validating the JSON descriptor")
        bosh(["validate", descriptor_str])

        # process and validate the invocation
        self.logger.info("Processing the JSON invocation")
        invocation_str = self.process_template_json(
            self.invocation,
            participant_id=participant_id,
            session_id=session_id,
            objs=objs,
            **kwargs,
            return_str=True,
        )
        self.logger.debug(f"Invocation string: {invocation_str}")
        self.logger.info("Validating the JSON invocation")
        bosh(["invocation", "-i", invocation_str, descriptor_str])

        # run as a subprocess so that stdout/error are captured in the log
        if self.simulate:
            self.run_command(
                ["bosh", "exec", "simulate", "-i", invocation_str, descriptor_str]
            )
        else:
            self.run_command(
                ["bosh", "exec", "launch", "--stream", descriptor_str, invocation_str]
            )

        return descriptor_str, invocation_str

    def get_participants_sessions_to_run(
        self, participant_id: Optional[str], session_id: Optional[str]
    ):
        """Generate a list of participant and session IDs to run.

        Specifically, this list will include participants who have BIDS data but
        who have not previously successfully completed the pipeline (according)
        to the bagel file.
        """
        self.check_pipeline_version()  # in case this is called outside of run()
        if self.layout.fpath_imaging_bagel.exists():
            bagel = Bagel.load(self.layout.fpath_imaging_bagel)
            participants_sessions_completed = set(
                bagel.get_completed_participants_sessions(
                    pipeline_name=self.pipeline_name,
                    pipeline_version=self.pipeline_version,
                    participant_id=participant_id,
                    session_id=session_id,
                )
            )
        else:
            participants_sessions_completed = {}

        for participant_session in self.doughnut.get_bidsified_participants_sessions(
            participant_id=participant_id, session_id=session_id
        ):
            if participant_session not in participants_sessions_completed:
                yield participant_session

    def run_single(self, participant_id: str, session_id: str):
        """Run pipeline on a single participant/session."""
        # set up PyBIDS database
        self.set_up_bids_db(
            dpath_bids_db=self.dpath_pipeline_bids_db,
            participant_id=participant_id,
            session_id=session_id,
        )

        # get container command
        container_command = self.process_container_config(
            participant_id=participant_id,
            session_id=session_id,
            bind_paths=[
                self.layout.dpath_bids,
                self.dpath_pipeline_output,
                self.dpath_pipeline_work,
                self.dpath_pipeline_bids_db,
            ],
        )

        # run pipeline with Boutiques
        return self.launch_boutiques_run(
            participant_id, session_id, container_command=container_command
        )

    def run_cleanup(self, **kwargs):
        """Run pipeline runner cleanup."""
        for dpath in [self.dpath_pipeline_bids_db, self.dpath_pipeline_work]:
            if dpath.exists():
                self.rm(dpath)
        return super().run_cleanup(**kwargs)
