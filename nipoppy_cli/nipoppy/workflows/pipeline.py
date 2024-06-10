"""Base class for pipeline workflows."""

from __future__ import annotations

import json
import logging
import re
from abc import ABC, abstractmethod
from functools import cached_property
from pathlib import Path
from typing import Optional

import bids
from pydantic import ValidationError

from nipoppy.config.boutiques import (
    BoutiquesConfig,
    get_boutiques_config_from_descriptor,
)
from nipoppy.config.pipeline import PipelineConfig
from nipoppy.utils import (
    BIDS_SESSION_PREFIX,
    BIDS_SUBJECT_PREFIX,
    StrOrPathLike,
    add_pybids_ignore_patterns,
    check_participant,
    check_session,
    create_bids_db,
    get_pipeline_tag,
    load_json,
    participant_id_to_bids_id,
    process_template_str,
    strip_session,
)
from nipoppy.workflows.base import BaseWorkflow


class BasePipelineWorkflow(BaseWorkflow, ABC):
    """A workflow for a pipeline that has a Boutiques descriptor."""

    def __init__(
        self,
        dpath_root: StrOrPathLike,
        name: str,
        pipeline_name: str,
        pipeline_version: Optional[str] = None,
        pipeline_step: Optional[str] = None,
        participant: str = None,
        session: str = None,
        fpath_layout: Optional[StrOrPathLike] = None,
        logger: Optional[logging.Logger] = None,
        dry_run=False,
    ):
        super().__init__(
            dpath_root=dpath_root,
            name=name,
            fpath_layout=fpath_layout,
            logger=logger,
            dry_run=dry_run,
        )
        self.pipeline_name = pipeline_name
        self.pipeline_version = pipeline_version
        self.pipeline_step = pipeline_step
        self.participant = check_participant(participant)
        self.session = check_session(session)

    @cached_property
    def dpaths_to_check(self) -> list[Path]:
        """Directory paths to create if needed during the setup phase."""
        return [self.dpath_pipeline]

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
        fpath_container = self.pipeline_config.get_fpath_container()
        if fpath_container is None:
            raise RuntimeError(
                f"No container image file specified in config for pipeline"
                f" {self.pipeline_name} {self.pipeline_version}"
            )

        elif not fpath_container.exists():
            raise FileNotFoundError(
                f"No container image file found at {fpath_container} for pipeline"
                f" {self.pipeline_name} {self.pipeline_version}"
            )
        return fpath_container

    @cached_property
    def descriptor(self) -> dict:
        """Load the pipeline step's Boutiques descriptor."""
        fpath_descriptor = self.pipeline_config.get_descriptor_file(
            step_name=self.pipeline_step
        )
        if fpath_descriptor is None:
            raise ValueError(
                "No descriptor file specified for pipeline"
                f" {self.pipeline_name} {self.pipeline_version}"
            )
        self.logger.info(f"Loading descriptor from {fpath_descriptor}")
        descriptor = load_json(fpath_descriptor)
        descriptor = self.config.apply_substitutions_to_json(descriptor)
        return descriptor

    @cached_property
    def invocation(self) -> dict:
        """Load the pipeline step's Boutiques invocation."""
        fpath_invocation = self.pipeline_config.get_invocation_file(
            step_name=self.pipeline_step
        )
        if fpath_invocation is None:
            raise ValueError(
                "No invocation file specified for pipeline"
                f" {self.pipeline_name} {self.pipeline_version}"
            )
        self.logger.info(f"Loading invocation from {fpath_invocation}")
        invocation = load_json(fpath_invocation)
        invocation = self.config.apply_substitutions_to_json(invocation)
        return invocation

    @cached_property
    def pybids_ignore_patterns(self) -> list[str]:
        """
        Load the pipeline step's PyBIDS ignore pattern list.

        Note: this does not apply any substitutions, since the subject/session
        patterns are always added.
        """
        fpath_pybids_ignore = self.pipeline_config.get_pybids_ignore_file(
            step_name=self.pipeline_step
        )

        # no file specified
        if fpath_pybids_ignore is None:
            return []

        # load patterns from file
        patterns = load_json(fpath_pybids_ignore)

        # validate format
        if not isinstance(patterns, list):
            raise ValueError(
                f"Expected a list of strings in {fpath_pybids_ignore}"
                f", got {patterns} ({type(patterns)})"
            )

        return [re.compile(pattern) for pattern in patterns]

    @cached_property
    def boutiques_config(self):
        """Get the Boutiques configuration."""
        try:
            boutiques_config = get_boutiques_config_from_descriptor(
                self.descriptor,
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
            self.logger.debug(f"\t{k}:".ljust(max_len + 3) + v)
        self.logger.debug(f"\t+ all attributes in: {objs}")

        template_json_str = process_template_str(
            json.dumps(template_json),
            objs=objs,
            **kwargs,
        )

        return template_json_str if return_str else json.loads(template_json_str)

    def set_up_bids_db(
        self,
        dpath_bids_db: StrOrPathLike,
        participant: Optional[str] = None,
        session: Optional[str] = None,
    ) -> bids.BIDSLayout:
        """Set up the BIDS database."""
        dpath_bids_db: Path = Path(dpath_bids_db)

        if participant is not None:
            add_pybids_ignore_patterns(
                current=self.pybids_ignore_patterns,
                new=f"^(?!/{BIDS_SUBJECT_PREFIX}({participant}))",
            )
        if session is not None:
            add_pybids_ignore_patterns(
                current=self.pybids_ignore_patterns,
                new=f".*?/{BIDS_SESSION_PREFIX}(?!{strip_session(session)})",
            )

        self.logger.info(
            f"Building BIDSLayout with {len(self.pybids_ignore_patterns)} ignore "
            f"patterns: {self.pybids_ignore_patterns}"
        )

        if dpath_bids_db.exists() and list(dpath_bids_db.iterdir()):
            self.logger.warning(
                f"Overwriting existing BIDS database directory: {dpath_bids_db}"
            )

        self.logger.debug(f"Path to BIDS data: {self.layout.dpath_bids}")
        bids_layout: bids.BIDSLayout = create_bids_db(
            dpath_bids=self.layout.dpath_bids,
            dpath_bids_db=dpath_bids_db,
            ignore_patterns=self.pybids_ignore_patterns,
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

    def check_dir(self, dpath: Path):
        """Create directory if it does not exist."""
        if not dpath.exists():
            self.mkdir(dpath, log_level=logging.WARNING)

    def check_pipeline_version(self):
        """Set the pipeline version based on the config if it is not given."""
        if self.pipeline_version is None:
            self.pipeline_version = self.config.get_pipeline_version(
                pipeline_name=self.pipeline_name
            )
            self.logger.warning(
                f"Pipeline version not specified, using version {self.pipeline_version}"
            )

    def run_setup(self, **kwargs):
        """Run pipeline setup."""
        to_return = super().run_setup(**kwargs)

        self.check_pipeline_version()

        for dpath in self.dpaths_to_check:
            self.check_dir(dpath)

        return to_return

    def run_main(self, **kwargs):
        """Run the pipeline."""
        for participant, session in self.get_participants_sessions_to_run(
            self.participant, self.session
        ):
            self.logger.info(f"Running on participant {participant}, session {session}")
            try:
                self.run_single(participant, session)
            except Exception as exception:
                self.logger.error(
                    f"Error running {self.pipeline_name} {self.pipeline_version}"
                    f" on participant {participant}, session {session}"
                    f": {exception}"
                )

    def run_cleanup(self, **kwargs):
        """Run pipeline cleanup."""
        if self.dpath_pipeline_work.exists():
            self.rm(self.dpath_pipeline_work)
        return super().run_cleanup(**kwargs)

    def get_participants_sessions_to_run(
        self, participant: Optional[str], session: Optional[str]
    ):
        """Return participant-session pairs to run the pipeline on."""
        # TODO add option in Boutiques descriptor of pipeline
        # 1. "manifest" (or "all"?)
        # 2. "downloaded" but not "organized" (from doughnut)
        # 3. "organized" but not "bidsified" (from doughnut)
        # 4. "bidsified" but not completed (from doughnut/bagel)
        # 5. "dataset" (i.e. apply on entire dataset, do not loop over anything)

        # for now just check the participants/sessions that have BIDS data
        return self.doughnut.get_bidsified_participants_sessions(
            participant=participant, session=session
        )

    @abstractmethod
    def run_single(self, participant: Optional[str], session: Optional[str]):
        """Run on a single participant/session."""
        pass

    def generate_fpath_log(
        self,
        dnames_parent: Optional[str | list[str]] = None,
        fname_stem: Optional[str] = None,
    ) -> Path:
        """Generate a log file path."""
        # make sure that pipeline version is not None
        self.check_pipeline_version()
        if dnames_parent is None:
            dnames_parent = get_pipeline_tag(
                pipeline_name=self.pipeline_name,
                pipeline_version=self.pipeline_version,
            )
        if fname_stem is None:
            fname_stem = get_pipeline_tag(
                pipeline_name=self.pipeline_name,
                pipeline_version=self.pipeline_version,
                participant=self.participant,
                session=self.session,
            )
        return super().generate_fpath_log(
            dnames_parent=dnames_parent, fname_stem=fname_stem
        )
