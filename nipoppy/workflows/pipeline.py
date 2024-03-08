"""Base class for pipeline workflows."""

import json
import logging
from abc import ABC, abstractmethod
from functools import cached_property
from pathlib import Path
from typing import Optional

import bids
from boutiques import bosh
from pydantic import ValidationError

from nipoppy.config.base import PipelineConfig
from nipoppy.config.boutiques import (
    BoutiquesConfig,
    get_boutiques_config_from_descriptor,
)
from nipoppy.config.singularity import prepare_singularity
from nipoppy.utils import (
    BIDS_SESSION_PREFIX,
    BIDS_SUBJECT_PREFIX,
    DPATH_DESCRIPTORS,
    check_participant,
    check_session,
    create_bids_db,
    get_pipeline_tag,
    load_json,
    participant_id_to_bids_id,
    process_template_str,
    strip_session,
)
from nipoppy.workflows.base import _Workflow


class _PipelineWorkflow(_Workflow, ABC):
    """A workflow for a pipeline that has a Boutiques descriptor."""

    def __init__(
        self,
        dpath_root: Path | str,
        pipeline_name: str,
        pipeline_version: str,
        participant=None,
        session=None,
        logger: Optional[logging.Logger] = None,
        dry_run=False,
    ):
        super().__init__(
            dpath_root=dpath_root,
            name=get_pipeline_tag(pipeline_name, pipeline_version),
            logger=logger,
            dry_run=dry_run,
        )
        self.pipeline_name = pipeline_name
        self.pipeline_version = pipeline_version
        self.participant = check_participant(participant)
        self.session = check_session(session)

    @cached_property
    def dpath_pipeline(self) -> Path:
        """Return the path to the pipeline's derivatives directory."""
        return self.layout.get_dpath_pipeline(
            pipeline_name=self.pipeline_name, pipeline_version=self.pipeline_version
        )

    @cached_property
    def dpath_pipeline_output(self) -> Path:
        """Return the path to the pipeline's output directory."""
        return self.layout.get_dpath_pipeline_output(
            pipeline_name=self.pipeline_name,
            pipeline_version=self.pipeline_version,
        )

    @cached_property
    def dpath_pipeline_work(self) -> Path:
        """Return the path to the pipeline's working directory."""
        return self.layout.get_dpath_pipeline_work(
            pipeline_name=self.pipeline_name,
            pipeline_version=self.pipeline_version,
            participant=self.participant,
            session=self.session,
        )

    @cached_property
    def dpath_pipeline_bids_db(self) -> Path:
        """Return the path to the pipeline's BIDS database directory."""
        return self.layout.get_dpath_bids_db(
            pipeline_name=self.pipeline_name,
            pipeline_version=self.pipeline_version,
            participant=self.participant,
            session=self.session,
        )

    @cached_property
    def pipeline_config(self) -> PipelineConfig:
        """Get the user config for the pipeline."""
        return self.config.get_pipeline_config(
            self.pipeline_name, self.pipeline_version
        )

    @cached_property
    def fpath_container(self) -> Path:
        """Return the full path to the pipeline's container."""
        fpath_container = (
            self.layout.dpath_containers / self.pipeline_config.get_container()
        )
        if not fpath_container.exists():
            raise FileNotFoundError(
                f"No container image file found at {fpath_container} for pipeline"
                f" {self.pipeline_name}, version {self.pipeline_version}"
            )
        return fpath_container

    @cached_property
    def descriptor(self) -> dict:
        """Load the pipeline's Boutiques descriptor."""
        # first check if the pipeline config has the descriptor itself
        descriptor = self.pipeline_config.DESCRIPTOR
        if descriptor is None:
            # TODO then check if the pipeline config specifies a path

            # finally check if there is a built-in descriptor
            fpath_descriptor_builtin = DPATH_DESCRIPTORS / f"{self.name}.json"
            try:
                descriptor = load_json(fpath_descriptor_builtin)
                self.logger.info("Using built-in descriptor")
            except FileNotFoundError:
                raise RuntimeError(
                    "No built-in descriptor found for pipeline"
                    f" {self.pipeline_name}, version {self.pipeline_version}"
                    # TODO dump a list of built-in descriptors
                )
        else:
            self.logger.info("Loaded descriptor from pipeline config")

        return descriptor

    @cached_property
    def invocation(self) -> dict:
        """Load the pipeline's Boutiques invocation."""
        # for now just get the invocation directly
        # TODO eventually add option to load from file
        return self.pipeline_config.INVOCATION

    def process_template_json(
        self,
        template_json: dict,
        participant: str,
        session: str,
        bids_id: Optional[str] = None,
        session_short: Optional[str] = None,
        objs: Optional[list] = None,
        return_str: bool = False,
        **kwargs,
    ):
        """Replace template strings in a JSON object."""
        if not (isinstance(participant, str) and isinstance(session, str)):
            raise ValueError(
                "participant and session must be strings"
                f", got {participant} ({type(participant)})"
                f" and {session} ({type(session)})"
            )

        if bids_id is None:
            bids_id = participant_id_to_bids_id(participant)
        if session_short is None:
            session_short = strip_session(session)

        if objs is None:
            objs = []
        objs.extend([self, self.layout])

        kwargs["participant"] = participant
        kwargs["session"] = session
        kwargs["bids_id"] = bids_id
        kwargs["session_short"] = session_short

        self.logger.debug("Available replacement strings: ")
        max_len = max(len(k) for k in kwargs)
        for k, v in kwargs.items():
            print(k, v)
            self.logger.debug(f"\t{k}:".ljust(max_len + 3) + v)
        self.logger.debug(f"\t+ all attributes in: {objs}")

        template_json_str = process_template_str(
            json.dumps(template_json),
            objs=objs,
            **kwargs,
        )

        if return_str:
            return template_json_str
        else:
            return json.loads(template_json_str)

    def get_boutiques_config(self, participant: str, session: str):
        """Get the Boutiques configuration."""
        try:
            boutiques_config = get_boutiques_config_from_descriptor(
                self.descriptor,
                func_to_apply=(
                    lambda json_data: self.process_template_json(
                        json_data,
                        participant=participant,
                        session=session,
                        return_str=False,
                    )
                ),
            )
        except ValidationError as exception:
            error_message = str(exception) + str(exception.errors())
            raise ValueError(
                f"Error when loading the Boutiques config from descriptor"
                f": {error_message}"
            )
        except RuntimeError as exception:
            self.logger.debug(
                "Caught exception when trying to load Boutiques config"
                f": {type(exception).__name__}: {exception}"
            )
            self.logger.debug(
                "Assuming Boutiques config is not in descriptor. Using default"
            )
            return BoutiquesConfig()

        self.logger.info(f"Loaded Boutiques config from descriptor: {boutiques_config}")
        return boutiques_config

    def set_up_bids_db(
        self,
        dpath_bids_db: Path | str,
        participant: Optional[str] = None,
        session: Optional[str] = None,
    ) -> bids.BIDSLayout:
        """Set up the BIDS database."""
        dpath_bids_db = Path(dpath_bids_db)

        if participant is not None:
            self.pipeline_config.add_pybids_ignore_patterns(
                f"^(?!/{BIDS_SUBJECT_PREFIX}({participant}))"
            )
        if session is not None:
            self.pipeline_config.add_pybids_ignore_patterns(
                f".*?/{BIDS_SESSION_PREFIX}(?!{strip_session(session)})"
            )

        pybids_ignore_patterns = self.pipeline_config.PYBIDS_IGNORE
        self.logger.info(
            f"Building BIDSLayout with {len(pybids_ignore_patterns)} ignore patterns:"
            f" {pybids_ignore_patterns}"
        )

        if dpath_bids_db.exists() and len(list(dpath_bids_db.iterdir())) > 0:
            self.logger.warning(
                f"Overwriting existing BIDS database directory: {dpath_bids_db}"
            )

        self.logger.debug(f"Path to BIDS data: {self.layout.dpath_bids}")
        bids_layout: bids.BIDSLayout = create_bids_db(
            dpath_bids=self.layout.dpath_bids,
            dpath_bids_db=dpath_bids_db,
            ignore_patterns=pybids_ignore_patterns,
            reset_database=True,
        )

        # list all the files in BIDSLayout
        # since we are selecting for specific a specific subject and
        # session, there should not be too many files
        filenames = bids_layout.get(return_type="filename")
        self.logger.debug(f"Found {len(filenames)} files in BIDS database:")
        for filename in filenames:
            self.logger.debug(filename)

        if len(filenames) == 0:
            self.logger.warning("BIDS database is empty")

        return bids_layout

    def run_setup(self, **kwargs):
        """Run pipeline setup."""
        to_return = super().run_setup(**kwargs)

        # make sure the pipeline config exists
        self.pipeline_config

        # create pipeline directories if needed
        for dpath in [
            self.dpath_pipeline,
            self.dpath_pipeline_output,
            self.dpath_pipeline_work,
        ]:
            if not dpath.exists():
                self.logger.warning(
                    f"Creating directory because it does not exist: {dpath}"
                )
                if not self.dry_run:
                    dpath.mkdir(parents=True, exist_ok=True)

        return to_return

    def run_main(self, **kwargs):
        """Run the pipeline."""
        for participant, session in self.get_participants_sessions_to_run(
            self.participant, self.session
        ):
            self.logger.info(
                f"Running {self.pipeline_name} {self.pipeline_version}"
                f" on participant {participant}, session {session}"
            )
            self.run_single(participant, session)

    def run_cleanup(self, **kwargs):
        """Run pipeline cleanup."""
        if self.dpath_pipeline_work.exists():
            self.run_command(["rm", "-rf", self.dpath_pipeline_work])
        return super().run_cleanup(**kwargs)

    def get_participants_sessions_to_run(
        self, participant: Optional[str], session: Optional[str]
    ):
        # TODO add option in Boutiques descriptor of pipeline
        # 1. "manifest" (or "all"?)
        # 2. "downloaded" (from doughnut)
        # 3. "organized" (from doughnut)
        # 4. "converted" (from doughnut)
        # 5. "dataset" (i.e. apply on entire dataset, do not loop over anything)

        # for now just check the participants/sessions that have BIDS data
        return self.doughnut.get_converted_participants_sessions(
            participant=participant, session=session
        )

    @abstractmethod
    def run_single(self, participant: Optional[str], session: Optional[str]):
        """Run on a single participant/session."""
        pass

    def generate_fpath_log(self) -> Path:
        return super().generate_fpath_log(
            fname_stem=get_pipeline_tag(
                pipeline_name=self.pipeline_name,
                pipeline_version=self.pipeline_version,
                participant=self.participant,
                session=self.session,
            )
        )


class PipelineRunner(_PipelineWorkflow):
    """Pipeline runner."""

    def __init__(
        self,
        dpath_root: Path | str,
        pipeline_name: str,
        pipeline_version: str,
        participant=None,
        session=None,
        simulate=False,
        logger: Optional[logging.Logger] = None,
        dry_run=False,
    ):
        super().__init__(
            dpath_root=dpath_root,
            pipeline_name=pipeline_name,
            pipeline_version=pipeline_version,
            participant=participant,
            session=session,
            logger=logger,
            dry_run=dry_run,
        )
        self.simulate = simulate

    def run_single(self, participant: str, session: str):
        """Run pipeline on a single participant/session."""
        # get singularity config
        singularity_config = self.pipeline_config.get_singularity_config()
        self.logger.debug(f"Initial Singularity config: {singularity_config}")

        # update singularity config with based on Boutiques config
        boutiques_config = self.get_boutiques_config(participant, session)
        self.logger.debug(f"Boutiques config: {boutiques_config}")
        if boutiques_config != BoutiquesConfig():
            self.logger.info("Updating Singularity config with config from descriptor")
            singularity_config.merge_args_and_env_vars(
                boutiques_config.get_singularity_config()
            )

        # set up PyBIDS database
        self.set_up_bids_db(
            dpath_bids_db=self.dpath_pipeline_bids_db,
            participant=participant,
            session=session,
        )
        singularity_config.add_bind_path(self.dpath_pipeline_bids_db)

        # update singularity config
        singularity_config.add_bind_path(self.layout.dpath_bids)
        singularity_config.add_bind_path(self.dpath_pipeline_output)
        singularity_config.add_bind_path(self.dpath_pipeline_work)
        self.logger.info(f"Using Singularity config: {singularity_config}")

        # get final singularity command
        singularity_command = prepare_singularity(
            singularity_config, check=True, logger=self.logger
        )

        # process and validate the descriptor
        self.logger.info("Processing the JSON descriptor")
        descriptor_str = self.process_template_json(
            self.descriptor,
            participant=participant,
            session=session,
            singularity_command=singularity_command,
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
            singularity_command=singularity_command,
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

    def run_cleanup(self, **kwargs):
        """Run pipeline runner cleanup."""
        if self.dpath_pipeline_bids_db.exists():
            self.run_command(["rm", "-rf", self.dpath_pipeline_bids_db])
        return super().run_cleanup(**kwargs)


class PipelineTracker(_PipelineWorkflow):
    """Pipeline tracker."""

    def run_setup(self, **kwargs):
        """Load/initialize the bagel file."""
        # TODO
        return super().run_setup(**kwargs)

    def run_single(self, participant: str, session: str):
        """Run tracker on a single participant/session."""
        # get list of paths

        # check status and add to bagel file

        # TODO handle potentially zipped archives

        pass

    def run_cleanup(self, **kwargs):
        """Save the bagel file."""
        return super().run_cleanup(**kwargs)
