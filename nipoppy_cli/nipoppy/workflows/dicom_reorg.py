"""DICOM file organization."""

import logging
import os
from pathlib import Path
from typing import Optional

import pydicom

from nipoppy.env import StrOrPathLike
from nipoppy.tabular.doughnut import update_doughnut
from nipoppy.utils import participant_id_to_bids_participant, session_id_to_bids_session
from nipoppy.workflows.base import BaseWorkflow


def is_derived_dicom(fpath: Path) -> bool:
    """
    Read a DICOM file's header and check if it is a derived file.

    Some BIDS converters (e.g. Heudiconv) do not support derived DICOM files.
    """
    dcm_info = pydicom.dcmread(fpath)
    img_types = dcm_info.ImageType
    return "DERIVED" in img_types


class DicomReorgWorkflow(BaseWorkflow):
    """Workflow for organizing raw DICOM files."""

    def __init__(
        self,
        dpath_root: StrOrPathLike,
        copy_files: bool = False,
        check_dicoms: bool = False,
        fpath_layout: Optional[StrOrPathLike] = None,
        logger: Optional[logging.Logger] = None,
        dry_run: bool = False,
    ):
        """Initialize the DICOM reorganization workflow."""
        super().__init__(
            dpath_root=dpath_root,
            name="dicom_reorg",
            fpath_layout=fpath_layout,
            logger=logger,
            dry_run=dry_run,
        )
        self.copy_files = copy_files
        self.check_dicoms = check_dicoms

    def get_fpaths_to_reorg(
        self,
        participant_id: str,
        session_id: str,
    ) -> list[Path]:
        """Get file paths to reorganize for a single participant and session."""
        dpath_downloaded = (
            self.layout.dpath_raw_imaging
            / self.dicom_dir_map.get_dicom_dir(
                participant_id=participant_id, session_id=session_id
            )
        )

        # make sure directory exists
        if not dpath_downloaded.exists():
            raise FileNotFoundError(
                f"Raw DICOM directory not found for participant {participant_id}"
                f" session {session_id}: {dpath_downloaded}"
            )

        # crawl through directory tree and get all file paths
        fpaths = []
        for dpath, _, fnames in os.walk(dpath_downloaded):
            fpaths.extend(Path(dpath, fname) for fname in fnames)
        return fpaths

    def apply_fname_mapping(
        self, fname_source: str, participant_id: str, session_id: str
    ) -> str:
        """
        Apply a mapping to the file name.

        This method does not change the file name by default, but it can be overridden
        if the file names need to be changed during reorganization (e.g. for easier
        BIDS conversion).
        """
        return fname_source

    def run_single(self, participant_id: str, session_id: str):
        """Reorganize downloaded DICOM files for a single participant and session."""
        # get paths to reorganize
        fpaths_to_reorg = self.get_fpaths_to_reorg(participant_id, session_id)

        dpath_reorganized: Path = (
            self.layout.dpath_sourcedata
            / participant_id_to_bids_participant(participant_id)
            / session_id_to_bids_session(session_id)
        )
        self.mkdir(dpath_reorganized)

        # do reorg
        for fpath_source in fpaths_to_reorg:
            # check file (though only error out if DICOM cannot be read)
            if self.check_dicoms:
                try:
                    if is_derived_dicom(fpath_source):
                        self.logger.warning(
                            f"Derived DICOM file detected: {fpath_source}"
                        )
                except Exception as exception:
                    raise RuntimeError(
                        f"Error checking DICOM file {fpath_source}: {exception}"
                    )

            fpath_dest = dpath_reorganized / self.apply_fname_mapping(
                fpath_source.name, participant_id=participant_id, session_id=session_id
            )

            # do not overwrite existing files
            if fpath_dest.exists():
                raise FileExistsError(
                    f"Cannot move file {fpath_source} to {fpath_dest}"
                    " because it already exists"
                )

            # either create symlinks or copy original files
            if not self.dry_run:
                if self.copy_files:
                    self.copy(fpath_source, fpath_dest)
                else:
                    fpath_source = os.path.relpath(fpath_source, fpath_dest.parent)
                    self.create_symlink(path_source=fpath_source, path_dest=fpath_dest)

        # update doughnut entry
        self.doughnut.set_status(
            participant_id=participant_id,
            session_id=session_id,
            col=self.doughnut.col_in_sourcedata,
            status=True,
        )

    def get_participants_sessions_to_run(self):
        """Return participant-session pairs to reorganize."""
        participants_sessions_organized = set(
            self.doughnut.get_organized_participants_sessions()
        )
        for participant_session in self.doughnut.get_downloaded_participants_sessions():
            if participant_session not in participants_sessions_organized:
                yield participant_session

    def run_setup(self):
        """Update the doughnut in case it is not up-to-date."""
        self.doughnut = update_doughnut(
            doughnut=self.doughnut,
            manifest=self.manifest,
            dicom_dir_map=self.dicom_dir_map,
            dpath_downloaded=self.layout.dpath_raw_imaging,
            dpath_organized=self.layout.dpath_sourcedata,
            dpath_bidsified=self.layout.dpath_bids,
            logger=self.logger,
        )

    def run_main(self):
        """Reorganize all downloaded DICOM files."""
        for (
            participant_id,
            session_id,
        ) in self.get_participants_sessions_to_run():
            try:
                self.run_single(participant_id, session_id)
            except Exception as exception:
                self.logger.error(
                    "Error reorganizing DICOM files for participant "
                    f"{participant_id} session {session_id}: {exception}"
                )

    def run_cleanup(self):
        """
        Clean up after main DICOM reorg part is run.

        Specifically:
        - Write updated doughnut file
        """
        self.save_tabular_file(self.doughnut, self.layout.fpath_doughnut)
        return super().run_cleanup()
