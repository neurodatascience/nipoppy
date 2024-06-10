"""Classes for the DICOM directory mapping."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from pydantic import Field, model_validator
from typing_extensions import Self

from nipoppy.layout import DEFAULT_LAYOUT_INFO
from nipoppy.tabular.base import BaseTabular, BaseTabularModel
from nipoppy.tabular.manifest import Manifest
from nipoppy.utils import (
    BIDS_SESSION_PREFIX,
    BIDS_SUBJECT_PREFIX,
    FIELD_DESCRIPTION_MAP,
)


class DicomDirMapModel(BaseTabularModel):
    """
    A file for mapping participant IDs to DICOM directories.

    Note: This class is called "model" to be consistent with Pydantic nomenclature,
    but it can be thought of as a schema for each row in the mapping file.
    """

    participant_id: str = Field(
        title="Participant ID", description=FIELD_DESCRIPTION_MAP["participant_id"]
    )
    session: str = Field(description=FIELD_DESCRIPTION_MAP["session"])
    participant_dicom_dir: str = Field(
        title="Participant's raw DICOM directory",
        description=(
            "Path to the participant's raw DICOM directory, relative to the dataset's"
            f"raw DICOM directory (default: {DEFAULT_LAYOUT_INFO.dpath_raw_dicom})"
        ),
    )

    @model_validator(mode="after")
    def validate_after(self) -> Self:
        """Validate participant_id and session fields."""
        if self.participant_id.startswith(BIDS_SUBJECT_PREFIX):
            raise ValueError(
                f'Participant ID should not start with "{BIDS_SUBJECT_PREFIX}"'
                f", got {self.participant_id}"
            )
        if not self.session.startswith(BIDS_SESSION_PREFIX):
            raise ValueError(
                f'Session should start with "{BIDS_SESSION_PREFIX}"'
                f", got {self.session}"
            )
        return self


class DicomDirMap(BaseTabular):
    """
    A dataset's DICOM directory mapping.

    This mapping is used during DICOM reorganization and doughnut generation.
    """

    # column names
    col_participant_id = "participant_id"
    col_session = "session"
    col_participant_dicom_dir = "participant_dicom_dir"

    index_cols = [col_participant_id, col_session]

    # set the model
    model = DicomDirMapModel

    _metadata = BaseTabular._metadata + [
        "col_participant_id",
        "col_session",
        "col_participant_dicom_dir",
        "index_cols",
        "model",
    ]

    @classmethod
    def load_or_generate(
        cls,
        manifest: Manifest,
        fpath_dicom_dir_map: str | Path | None,
        participant_first: Optional[bool],
        validate: bool = True,
    ) -> Self:
        """Load or generate a DicomDirMap instance.

        Parameters
        ----------
        manifest : :class:`nipoppy.tabular.manifest.Manifest`
            Manifest for generating the mapping (not used if ``fpath_dicom_dir_map``
            is not ``None``).
        fpath_dicom_dir_map : str | Path | None
            Path to a custom DICOM directory mapping file. If ``None``,
            the DICOM directory mapping will be generated from the manifest.
        participant_first : bool
            Whether the generated uses ``<PARTICIPANT>/<SESSION>`` order
            (True) or ``<SESSION>/<PARTICIPANT>`` (False). Not used if
            ``fpath_dicom_dir_map`` is not ``None``
        validate : bool, optional
            Whether to validate (through Pydantic) the created object,
            by default ``True``

        Returns
        -------
        :class:`nipoppy.tabular.dicom_dir_map.DicomDirMap`
        """
        # if these is a custom dicom_dir_map, use it
        if fpath_dicom_dir_map is not None:
            return cls.load(Path(fpath_dicom_dir_map), validate=validate)

        # else depends on participant_first or no
        else:
            data_dicom_dir_map = []
            for participant, session in manifest.get_participants_sessions():
                if participant_first is not False:
                    participant_dicom_dir = f"{participant}/{session}"
                else:
                    participant_dicom_dir = f"{session}/{participant}"
                data_dicom_dir_map.append(
                    {
                        cls.col_participant_id: participant,
                        cls.col_session: session,
                        cls.col_participant_dicom_dir: participant_dicom_dir,
                    }
                )
            dicom_dir_map = cls(data=data_dicom_dir_map)
            if validate:
                dicom_dir_map.validate()
            return dicom_dir_map

    def get_dicom_dir(self, participant: str, session: str) -> str:
        """Return the participant's raw DICOM directory for a given session.

        Parameters
        ----------
        participant : str
            Participant ID, without the BIDS prefix
        session : str
            Session, with the BIDS prefix
        """
        return self.set_index(self.index_cols).loc[participant, session].item()
