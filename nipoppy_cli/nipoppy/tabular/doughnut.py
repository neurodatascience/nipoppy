"""Class for the doughnut file."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from pydantic import Field
from typing_extensions import Self

from nipoppy.logger import get_logger
from nipoppy.tabular.dicom_dir_map import DicomDirMap
from nipoppy.tabular.manifest import Manifest, ManifestModel
from nipoppy.utils import (
    FIELD_DESCRIPTION_MAP,
    StrOrPathLike,
    participant_id_to_bids_id,
    participant_id_to_dicom_id,
)


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
    dicom_id: str = Field(
        title="DICOM ID",
        description="Participant identifier used in DICOM file names/paths",
    )
    bids_id: str = Field(title="BIDS ID", description=FIELD_DESCRIPTION_MAP["bids_id"])
    downloaded: bool = Field(description="Whether files are available on disk")
    organized: bool = Field(
        description="Whether files have been organized in the sourcedata directory"
    )
    bidsified: bool = Field(
        title="BIDSified", description="Whether files have been converted to BIDS"
    )


class Doughnut(Manifest):
    """A dataset's doughnut, for tracking DICOM-to-BIDS conversion status."""

    # column names
    col_participant_dicom_dir = "participant_dicom_dir"
    col_dicom_id = "dicom_id"
    col_bids_id = "bids_id"
    col_downloaded = "downloaded"
    col_organized = "organized"
    col_bidsified = "bidsified"

    status_cols = [col_downloaded, col_organized, col_bidsified]

    # set the model
    model = DoughnutModel

    index_cols = [Manifest.col_participant_id, Manifest.col_session]

    _metadata = Manifest._metadata + [
        "col_participant_dicom_dir",
        "col_dicom_id",
        "col_bids_id",
        "col_downloaded",
        "col_organized",
        "col_bidsified",
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

    def get_status(self, participant: str, session: str, col: str) -> bool:
        """Get one of the statuses for an existing record."""
        col = self._check_status_col(col)
        return self.set_index(self.index_cols).loc[(participant, session), col]

    def set_status(
        self, participant: str, session: str, col: str, status: bool
    ) -> Self:
        """Set one of the statuses for an existing record."""
        col = self._check_status_col(col)
        status = self._check_status_value(status)
        self.set_index(self.index_cols, inplace=True)
        self.loc[(participant, session), col] = status
        return self.reset_index(inplace=True)

    def _get_participant_sessions_helper(
        self,
        status_col: str,
        participant: Optional[str] = None,
        session: Optional[str] = None,
    ):
        """Get subset of participants/sessions based on a status column."""
        doughnut_subset: Doughnut = self.loc[self[status_col]]
        return doughnut_subset.get_participants_sessions(
            participant=participant, session=session
        )

    def get_downloaded_participants_sessions(
        self,
        participant: Optional[str] = None,
        session: Optional[str] = None,
    ):
        """Get participants and sessions with downloaded data."""
        return self._get_participant_sessions_helper(
            self.col_downloaded, participant=participant, session=session
        )

    def get_organized_participants_sessions(
        self,
        participant: Optional[str] = None,
        session: Optional[str] = None,
    ):
        """Get participants and sessions with organized data."""
        return self._get_participant_sessions_helper(
            self.col_organized, participant=participant, session=session
        )

    def get_bidsified_participants_sessions(
        self,
        participant: Optional[str] = None,
        session: Optional[str] = None,
    ):
        """Get participants and sessions with BIDS data."""
        return self._get_participant_sessions_helper(
            self.col_bidsified, participant=participant, session=session
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
            dpath_participant = dpath / dname_subdirectory
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
        participant = manifest_record[manifest.col_participant_id]
        session = manifest_record[manifest.col_session]

        # get DICOM dir
        participant_dicom_dir = dicom_dir_map.get_dicom_dir(
            participant=participant, session=session
        )

        # get DICOM and BIDS IDs
        dicom_id = participant_id_to_dicom_id(participant)
        bids_id = participant_id_to_bids_id(participant)

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
                dpath=dpath_organized, dname_subdirectory=Path(dicom_id, session)
            )
            status_bidsified = check_status(
                dpath=dpath_bidsified, dname_subdirectory=Path(bids_id, session)
            )

        doughnut_records.append(
            {
                Doughnut.col_participant_id: participant,
                Doughnut.col_visit: manifest_record[Manifest.col_visit],
                Doughnut.col_session: session,
                Doughnut.col_datatype: manifest_record[Manifest.col_datatype],
                Doughnut.col_participant_dicom_dir: participant_dicom_dir,
                Doughnut.col_dicom_id: dicom_id,
                Doughnut.col_bids_id: bids_id,
                Doughnut.col_downloaded: status_downloaded,
                Doughnut.col_organized: status_organized,
                Doughnut.col_bidsified: status_bidsified,
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
