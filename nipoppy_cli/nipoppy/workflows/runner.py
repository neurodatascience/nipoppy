"""PipelineRunner workflow."""

import logging
from functools import cached_property
from pathlib import Path
from typing import Optional

from boutiques import bosh

from nipoppy.config.boutiques import BoutiquesConfig
from nipoppy.config.container import ContainerConfig, prepare_container
from nipoppy.utils import StrOrPathLike
from nipoppy.workflows.pipeline import BasePipelineWorkflow


class PipelineRunner(BasePipelineWorkflow):
    """Pipeline runner."""

    def __init__(
        self,
        dpath_root: StrOrPathLike,
        pipeline_name: str,
        pipeline_version: Optional[str] = None,
        pipeline_step: Optional[str] = None,
        participant: str = None,
        session: str = None,
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
            participant=participant,
            session=session,
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
        participant: str,
        session: str,
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
                participant=participant,
                session=session,
            )
        )
        self.logger.debug(f"Initial container config: {container_config}")

        # get and process Boutiques config
        boutiques_config = BoutiquesConfig(
            **self.process_template_json(
                self.boutiques_config.model_dump(),
                participant=participant,
                session=session,
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
        self, participant: str, session: str, objs: Optional[list] = None, **kwargs
    ):
        """Launch a pipeline run using Boutiques."""
        # process and validate the descriptor
        self.logger.info("Processing the JSON descriptor")
        descriptor_str = self.process_template_json(
            self.descriptor,
            participant=participant,
            session=session,
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
            participant=participant,
            session=session,
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

    def run_single(self, participant: str, session: str):
        """Run pipeline on a single participant/session."""
        # set up PyBIDS database
        self.set_up_bids_db(
            dpath_bids_db=self.dpath_pipeline_bids_db,
            participant=participant,
            session=session,
        )

        # get container command
        container_command = self.process_container_config(
            participant=participant,
            session=session,
            bind_paths=[
                self.layout.dpath_bids,
                self.dpath_pipeline_output,
                self.dpath_pipeline_work,
                self.dpath_pipeline_bids_db,
            ],
        )

        # run pipeline with Boutiques
        self.launch_boutiques_run(
            participant, session, container_command=container_command
        )

    def run_cleanup(self, **kwargs):
        """Run pipeline runner cleanup."""
        if self.dpath_pipeline_bids_db.exists():
            self.rm(self.dpath_pipeline_bids_db)
        return super().run_cleanup(**kwargs)
