"""Example script for custom DICOM reorganization."""

import argparse
from pathlib import Path

from nipoppy.logger import add_logfile
from nipoppy.workflows import DicomReorgWorkflow


class CustomDicomReorgWorkflow(DicomReorgWorkflow):
    """Custom workflow class that overrides two methods from DicomReorgWorkflow."""

    def get_fpaths_to_reorg(self, participant_id: str, session_id: str) -> list[Path]:
        """
        Get full file paths to reorganize for a single participant and session.

        Here we return a list with only a single path, but more than one path
        can be specified.
        """
        # self.layout.dpath_raw_dicom will dynamically generate the path to the
        # dataset's (unorganized) raw imaging data
        return [self.layout.dpath_raw_imaging / participant_id / f"{session_id}.tar.gz"]

    def apply_fname_mapping(
        self, fname_source: str, participant_id: str, session_id: str
    ) -> str:
        """
        Name the files differently in the sourcedata directory.

        Here we ignore the fname_source and (original filename) and return a string
        that will be used as the new filename.

        Note: this only controls the name of the file. Its parent directories will
        have fixed names that cannot be changed.
        """
        return f"{participant_id}-{session_id}.tar.gz"


if __name__ == "__main__":
    # use a command-line parser
    parser = argparse.ArgumentParser(
        description="Run the custom DICOM reorganization workflow."
    )
    parser.add_argument(
        "--dataset-root",
        type=Path,
        required=True,
        help="Root directory of Nipoppy dataset",
    )
    args = parser.parse_args()

    # initialize workflow
    workflow = CustomDicomReorgWorkflow(dpath_root=args.dataset_root)

    # set up logging to a file
    logger = workflow.logger
    add_logfile(logger, workflow.generate_fpath_log())

    # run the workflow
    try:
        workflow.run()
    except Exception:
        logger.exception(
            "An error occurred with the custom DICOM reorganization script"
        )
