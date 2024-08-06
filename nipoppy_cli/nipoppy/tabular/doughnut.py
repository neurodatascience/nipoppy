"""Class for the doughnut file."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from pydantic import Field
from typing_extensions import Self

from nipoppy.env import StrOrPathLike
from nipoppy.logger import get_logger
from nipoppy.tabular.dicom_dir_map import DicomDirMap
from nipoppy.tabular.manifest import Manifest, ManifestModel
from nipoppy.utils import participant_id_to_bids_participant, session_id_to_bids_session


class DoughnutModel(ManifestModel):
    """
    An internally- or user-generated file to keep track of the BIDS conversion process.

    Should contain exactly the same data as the manifest, with some additional columns.

    Note: This class is called "model" to be consistent with Pydantic nomenclature,
    but it can be thought of as a schema for each row in the doughnut file.
    """

    participant_dicom_dir: str = Field(
        title="Participant DICOM directory",
        description=(
            "Path to the directory containing raw DICOMs "
            "(in potentially messy tree structure) for the participant-visit pair, "
            "relative to the raw data directory"
        ),
    )
    in_raw_imaging: bool = Field(description="Whether files are available on disk")
    in_sourcedata: bool = Field(
        description="Whether files have been organized in the sourcedata directory"
    )
    in_bids: bool = Field(
        title="BIDSified", description="Whether files have been converted to BIDS"
    )


class Doughnut(Manifest):
    """A dataset's doughnut, for tracking DICOM-to-BIDS conversion status."""

    # column names
    col_participant_dicom_dir = "participant_dicom_dir"
    col_in_raw_imaging = "in_raw_imaging"
    col_in_sourcedata = "in_sourcedata"
    col_in_bids = "in_bids"

    status_cols = [col_in_raw_imaging, col_in_sourcedata, col_in_bids]

    # set the model
    model = DoughnutModel

    index_cols = [Manifest.col_participant_id, Manifest.col_session_id]

    _metadata = Manifest._metadata + [
        "col_participant_dicom_dir",
        "col_in_raw_imaging",
        "col_in_sourcedata",
        "col_in_bids",
    ]

    @classmethod
    def _check_status_col(cls, col: str) -> str:
        if col not in cls.status_cols:
            raise ValueError(
                f"Invalid status column: {col}. Must be one of {cls.status_cols}"
            )
        return col

    @classmethod
    def _check_status_value(cls, value: bool) -> bool:
        if not isinstance(value, bool):
            raise ValueError(f"Invalid status value: {value}. Must be a boolean")
        return value

    def get_status(self, participant_id: str, session_id: str, col: str) -> bool:
        """Get one of the statuses for an existing record."""
        col = self._check_status_col(col)
        return self.set_index(self.index_cols).loc[(participant_id, session_id), col]

    def set_status(
        self, participant_id: str, session_id: str, col: str, status: bool
    ) -> Self:
        """Set one of the statuses for an existing record."""
        col = self._check_status_col(col)
        status = self._check_status_value(status)
        self.set_index(self.index_cols, inplace=True)
        self.loc[(participant_id, session_id), col] = status
        return self.reset_index(inplace=True)

    def _get_participant_sessions_helper(
        self,
        status_col: str,
        participant_id: Optional[str] = None,
        session_id: Optional[str] = None,
    ):
        """Get subset of participants/sessions based on a status column."""
        doughnut_subset: Doughnut = self.loc[self[status_col]]
        return doughnut_subset.get_participants_sessions(
            participant_id=participant_id, session_id=session_id
        )

    def get_downloaded_participants_sessions(
        self,
        participant_id: Optional[str] = None,
        session_id: Optional[str] = None,
    ):
        """Get participants and sessions with downloaded data."""
        return self._get_participant_sessions_helper(
            self.col_in_raw_imaging,
            participant_id=participant_id,
            session_id=session_id,
        )

    def get_organized_participants_sessions(
        self,
        participant_id: Optional[str] = None,
        session_id: Optional[str] = None,
    ):
        """Get participants and sessions with organized data."""
        return self._get_participant_sessions_helper(
            self.col_in_sourcedata, participant_id=participant_id, session_id=session_id
        )

    def get_bidsified_participants_sessions(
        self,
        participant_id: Optional[str] = None,
        session_id: Optional[str] = None,
    ):
        """Get participants and sessions with BIDS data."""
        return self._get_participant_sessions_helper(
            self.col_in_bids, participant_id=participant_id, session_id=session_id
        )


def generate_doughnut(
    manifest: Manifest,
    dicom_dir_map: DicomDirMap,
    dpath_downloaded: Optional[StrOrPathLike] = None,
    dpath_organized: Optional[StrOrPathLike] = None,
    dpath_bidsified: Optional[StrOrPathLike] = None,
    empty=False,
    logger: Optional[logging.Logger] = None,
) -> Doughnut:
    """Generate a doughnut object."""

    def check_status(
        dpath: Optional[StrOrPathLike],
        dname_subdirectory: StrOrPathLike,
    ):
        dname_subdirectory = Path(dname_subdirectory)
        if dpath is None:
            status = False
        else:
            dpath = Path(dpath)
            dpath_participant: Path = dpath / dname_subdirectory
            if dpath_participant.exists():
                status = next(dpath_participant.iterdir(), None) is not None
            else:
                status = False
            logger.debug(f"Status for {dpath_participant}: {status}")
        return status

    if logger is None:
        logger = get_logger("generate_doughnut")

    # get participants/sessions with imaging data
    logger.debug(f"Full manifest:\n{manifest}")
    manifest_imaging_only = manifest.get_imaging_subset()
    logger.debug(f"Imaging-only manifest:\n{manifest_imaging_only}")

    doughnut_records = []
    for _, manifest_record in manifest_imaging_only.iterrows():
        participant_id = manifest_record[manifest.col_participant_id]
        session_id = manifest_record[manifest.col_session_id]

        # get DICOM dir
        participant_dicom_dir = dicom_dir_map.get_dicom_dir(
            participant_id=participant_id, session_id=session_id
        )

        # get BIDS IDs
        bids_participant = participant_id_to_bids_participant(participant_id)
        bids_session = session_id_to_bids_session(session_id)

        if empty:
            status_downloaded = False
            status_organized = False
            status_bidsified = False
        else:
            status_downloaded = check_status(
                dpath=dpath_downloaded,
                dname_subdirectory=participant_dicom_dir,
            )
            status_organized = check_status(
                dpath=dpath_organized,
                dname_subdirectory=Path(bids_participant, bids_session),
            )
            status_bidsified = check_status(
                dpath=dpath_bidsified,
                dname_subdirectory=Path(bids_participant, bids_session),
            )

        doughnut_records.append(
            {
                Doughnut.col_participant_id: participant_id,
                Doughnut.col_visit_id: manifest_record[Manifest.col_visit_id],
                Doughnut.col_session_id: session_id,
                Doughnut.col_datatype: manifest_record[Manifest.col_datatype],
                Doughnut.col_participant_dicom_dir: participant_dicom_dir,
                Doughnut.col_in_raw_imaging: status_downloaded,
                Doughnut.col_in_sourcedata: status_organized,
                Doughnut.col_in_bids: status_bidsified,
            }
        )

    doughnut = Doughnut(doughnut_records)
    logger.debug(f"Generated doughnut:\n{doughnut}")
    return doughnut


def update_doughnut(
    doughnut: Doughnut,
    manifest: Manifest,
    dicom_dir_map: DicomDirMap,
    dpath_downloaded: Optional[StrOrPathLike] = None,
    dpath_organized: Optional[StrOrPathLike] = None,
    dpath_bidsified: Optional[StrOrPathLike] = None,
    empty=False,
    logger: Optional[logging.Logger] = None,
) -> Doughnut:
    """Update an existing doughnut file."""
    if logger is None:
        logger = get_logger("update_doughnut")

    logger.debug(f"Original doughnut:\n{doughnut}")
    logger.debug(f"Manifest:\n{manifest}")
    manifest_subset = manifest.get_diff(doughnut, cols=doughnut.index_cols)
    logger.debug(
        "Manifest subset (difference between manifest and doughnut)"
        f":\n{manifest_subset}"
    )

    updated_doughnut = doughnut.concatenate(
        generate_doughnut(
            manifest=manifest_subset,
            dicom_dir_map=dicom_dir_map,
            dpath_downloaded=dpath_downloaded,
            dpath_organized=dpath_organized,
            dpath_bidsified=dpath_bidsified,
            empty=empty,
            logger=logger,
        )
    )

    logger.debug(f"Updated doughnut:\t{updated_doughnut}")

    return updated_doughnut
