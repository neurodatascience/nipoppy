"""PipelineTracker workflow."""

import tarfile
from collections.abc import Iterable
from pathlib import Path

from nipoppy.config.pipeline_step import AnalysisLevelType
from nipoppy.config.tracker import TrackerConfig
from nipoppy.env import EXT_TAR, StrOrPathLike
from nipoppy.exceptions import NipoppyError
from nipoppy.logger import get_logger
from nipoppy.tabular.processing_status import ProcessingStatusTable
from nipoppy.workflows.pipeline import BasePipelineWorkflow

logger = get_logger()


class PipelineTracker(BasePipelineWorkflow):
    """Pipeline tracker."""

    progress_bar_description = "Tracking..."

    def __init__(
        self,
        dpath_root: StrOrPathLike,
        pipeline_name: str,
        pipeline_version: str | None = None,
        pipeline_step: str | None = None,
        participant_id: str = None,
        session_id: str = None,
        n_jobs: int = 1,
        fpath_layout: StrOrPathLike | None = None,
        verbose: bool = False,
        dry_run: bool = False,
    ):
        super().__init__(
            dpath_root=dpath_root,
            name="track_processing",
            pipeline_name=pipeline_name,
            pipeline_version=pipeline_version,
            pipeline_step=pipeline_step,
            participant_id=participant_id,
            session_id=session_id,
            n_jobs=n_jobs,
            fpath_layout=fpath_layout,
            verbose=verbose,
            dry_run=dry_run,
            _skip_logfile=True,
            _show_progress=True,
        )

    def run_setup(self):
        """Load/initialize the processing status file."""
        rv = super().run_setup()
        if self.study.layout.fpath_processing_status.exists():
            try:
                self.processing_status_table = ProcessingStatusTable.load(
                    self.study.layout.fpath_processing_status
                )
                logger.info(
                    f"Found existing processing status file with shape"
                    f" {self.processing_status_table.shape}"
                    f" at {self.study.layout.fpath_processing_status}"
                )
            except NipoppyError as e:
                if "Error when validating the " in str(e):
                    logger.warning(
                        "Failed to load existing processing status file at "
                        f"{self.study.layout.fpath_processing_status}. Generating a new"
                        f" processing status table.\nOriginal error:\n{e}"
                    )
                    self.processing_status_table = ProcessingStatusTable()
        else:
            self.processing_status_table = ProcessingStatusTable()
            logger.info("Initialized empty processing status table")
        return rv

    def check_status(
        self,
        relative_paths: StrOrPathLike,
        relative_dpath_tarred: StrOrPathLike | None = None,
    ):
        """Check the processing status based on a list of expected paths."""
        # collect list of paths in tarball if it exists
        paths_tarred = []
        if relative_dpath_tarred is not None:
            fpath_tarball = (
                self.dpath_pipeline_output / f"{relative_dpath_tarred}{EXT_TAR}"
            )
            if fpath_tarball.exists():
                with tarfile.open(fpath_tarball) as tarball:
                    paths_tarred = tarball.getnames()

        any_incomplete = False

        for relative_path in relative_paths:
            relative_path = Path(relative_path)
            absolute_path = self.dpath_pipeline_output / relative_path
            logger.debug(f"Checking path {absolute_path}")

            matches_glob = list(self.dpath_pipeline_output.glob(str(relative_path)))
            logger.debug(f"Matches: {matches_glob}")

            if matches_glob:
                # Check for broken symlinks (e.g. git-annex without content)
                if any(p.is_symlink() and not p.exists() for p in matches_glob):
                    any_incomplete = True
            else:
                # Path.glob() with literal paths does not return broken symlinks,
                # so check directly whether the path is a broken symlink
                if absolute_path.is_symlink() and not absolute_path.exists():
                    any_incomplete = True
                    continue

                # also check tarball paths if applicable/needed
                if relative_dpath_tarred is not None:
                    # NOTE
                    # The behaviour of Path.match() is not exactly the same as
                    # glob but it should be good enough for now. What we really
                    # need is Path.full_match(), but that was only introduced
                    # in Python 3.13
                    matches_tarred = [
                        path_tarred
                        for path_tarred in paths_tarred
                        if Path(path_tarred).match(
                            str(
                                Path(relative_path).relative_to(
                                    Path(relative_dpath_tarred).parent
                                )
                            ),
                        )
                    ]
                    logger.debug(f"Matches in tarball: {matches_tarred}")
                else:
                    matches_tarred = []

                if not matches_tarred:
                    return ProcessingStatusTable.status_fail

        if any_incomplete:
            return ProcessingStatusTable.status_unavailable

        return ProcessingStatusTable.status_success

    def get_participants_sessions_to_run(
        self, participant_id: str | None, session_id: str | None
    ):
        """Get participant-session pairs with BIDS data to run the tracker on."""
        return self.curation_status_table.get_bidsified_participants_sessions(
            participant_id=participant_id, session_id=session_id
        )

    @staticmethod
    def apply_analysis_level(
        participants_sessions: Iterable[str],
        analysis_level: AnalysisLevelType,
    ) -> list[tuple[str]]:
        """Tracker: level is always participant-session."""
        return list(participants_sessions)

    def run_single(self, participant_id: str, session_id: str):
        """Run tracker on a single participant/session."""
        # replace template strings in the tracker config
        tracker_config = TrackerConfig(
            **self.process_template_json(
                self.tracker_config.model_dump(mode="json"),
                participant_id=participant_id,
                session_id=session_id,
            )
        )

        # check status and update processing status file
        status = self.check_status(
            tracker_config.PATHS, tracker_config.PARTICIPANT_SESSION_DIR
        )
        logger.debug(f"Status: {status}")
        processing_status_record = {
            ProcessingStatusTable.col_participant_id: participant_id,
            ProcessingStatusTable.col_session_id: session_id,
            ProcessingStatusTable.col_pipeline_name: self.pipeline_name,
            ProcessingStatusTable.col_pipeline_version: self.pipeline_version,
            ProcessingStatusTable.col_pipeline_step: self.pipeline_step,
            ProcessingStatusTable.col_status: status,
        }
        return processing_status_record

    def _update_status_file(self):
        """Update the processing status file."""
        self.processing_status_table = (
            self.processing_status_table.add_or_update_records(self.run_single_results)
        )
        logger.info(
            "New/updated processing status table shape: "
            f"{self.processing_status_table.shape}"
        )
        self.processing_status_table.save_with_backup(
            self.study.layout.fpath_processing_status,
            dry_run=self.dry_run,
        )

    def run_main(self):
        """Run the tracker workflow."""
        super().run_main()
        self._update_status_file()
