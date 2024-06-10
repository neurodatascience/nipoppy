"""PipelineTracker workflow."""

import logging
from typing import List, Optional

from pydantic import TypeAdapter

from nipoppy.config.tracker import TrackerConfig, check_tracker_configs
from nipoppy.tabular.bagel import Bagel
from nipoppy.utils import StrOrPathLike, load_json
from nipoppy.workflows.pipeline import BasePipelineWorkflow


class PipelineTracker(BasePipelineWorkflow):
    """Pipeline tracker."""

    def __init__(
        self,
        dpath_root: StrOrPathLike,
        pipeline_name: str,
        pipeline_version: Optional[str] = None,
        participant: str = None,
        session: str = None,
        fpath_layout: Optional[StrOrPathLike] = None,
        logger: Optional[logging.Logger] = None,
        dry_run: bool = False,
    ):
        super().__init__(
            dpath_root=dpath_root,
            name="track",
            pipeline_name=pipeline_name,
            pipeline_version=pipeline_version,
            participant=participant,
            session=session,
            fpath_layout=fpath_layout,
            logger=logger,
            dry_run=dry_run,
        )
        self.bagel: Bagel = Bagel()  # may get overwritten

    def run_setup(self, **kwargs):
        """Load/initialize the bagel file."""
        if self.layout.fpath_imaging_bagel.exists():
            self.bagel = Bagel.load(self.layout.fpath_imaging_bagel)
            self.logger.info(
                f"Found existing bagel with shape {self.bagel.shape}"
                f" at {self.layout.fpath_imaging_bagel}"
            )
        else:
            self.bagel = Bagel()
            self.logger.info("Initialized empty bagel")
        return super().run_setup(**kwargs)

    def check_status(self, relative_paths: StrOrPathLike):
        """Check the processing status based on a list of expected paths."""
        for relative_path in relative_paths:
            self.logger.debug(
                f"Checking path {self.dpath_pipeline_output / relative_path}"
            )

            # TODO handle potentially zipped archives
            matches = list(self.dpath_pipeline_output.glob(str(relative_path)))
            self.logger.debug(f"Matches: {matches}")
            if not matches:
                return Bagel.status_fail

        return Bagel.status_success

    def run_single(self, participant: str, session: str):
        """Run tracker on a single participant/session."""
        # load tracker configs from file
        fpath_tracker_config = self.pipeline_config.TRACKER_CONFIG_FILE
        if fpath_tracker_config is None:
            raise ValueError(
                f"No tracker config file specified for pipeline {self.pipeline_name}"
                f" {self.pipeline_version}"
            )
        # replace template strings
        tracker_configs = self.process_template_json(
            load_json(fpath_tracker_config),
            participant=participant,
            session=session,
        )
        # convert to list of TrackerConfig objects and validate
        tracker_configs = TypeAdapter(List[TrackerConfig]).validate_python(
            tracker_configs
        )
        tracker_configs = check_tracker_configs(tracker_configs)

        if len(tracker_configs) > 1:
            self.logger.warning(
                f"{len(tracker_configs)} tracker configs found for"
                f" pipeline {self.pipeline_name} {self.pipeline_version}"
                ". Currently only one config is supported (will use the first one)"
            )
        tracker_config = tracker_configs[0]

        # check status and update bagel
        status = self.check_status(tracker_config.PATHS)
        self.bagel = self.bagel.add_or_update_records(
            {
                Bagel.col_participant_id: participant,
                Bagel.col_session: session,
                Bagel.col_pipeline_name: self.pipeline_name,
                Bagel.col_pipeline_version: self.pipeline_version,
                Bagel.col_pipeline_complete: status,
            }
        )
        return status

    def run_cleanup(self, **kwargs):
        """Save the bagel file."""
        self.logger.info(f"New/updated bagel shape: {self.bagel.shape}")
        self.save_tabular_file(self.bagel, self.layout.fpath_imaging_bagel)
        return super().run_cleanup(**kwargs)
