"""Class for the dataset manifest."""

from __future__ import annotations

from typing import Optional

import pandas as pd
from pydantic import ConfigDict, Field, model_validator
from typing_extensions import Self

from nipoppy.tabular.base import BaseTabular, BaseTabularModel
from nipoppy.utils import FIELD_DESCRIPTION_MAP, check_participant_id, check_session_id


class ManifestModel(BaseTabularModel):
    """
    A user-provided listing of participant and visits available in the dataset.

    Note: This class is called "model" to be consistent with Pydantic nomenclature,
    but it can be thought of as a schema for each row in the manifest file.
    """

    participant_id: str = Field(
        title="Participant ID", description=FIELD_DESCRIPTION_MAP["participant_id"]
    )
    visit_id: str = Field(description=FIELD_DESCRIPTION_MAP["visit_id"])
    session_id: Optional[str] = Field(description=FIELD_DESCRIPTION_MAP["session_id"])
    datatype: Optional[list[str]] = Field(
        description=(
            "Imaging datatype, as recognized by BIDS (see "
            "https://bids-specification.readthedocs.io/en/stable/common-principles.html)"  # noqa E501
        )
    )

    @classmethod
    def _validate_before_fields(cls, data: dict):
        """Validate manifest-specific fields."""
        datatype = data.get(Manifest.col_datatype)
        if datatype is not None and not isinstance(datatype, list):
            try:
                data[Manifest.col_datatype] = pd.eval(datatype)
            except Exception:
                raise ValueError(
                    f"Invalid datatype: {datatype} ({type(datatype)}))"
                    ". Must be a list, a string representation of a list"
                    ", or left empty"
                )
        return data

    @model_validator(mode="after")
    def validate_after(self) -> Self:
        """Validate fields after instance creation."""
        check_participant_id(self.participant_id, raise_error=True)
        check_session_id(self.session_id, raise_error=True)
        return self

    # allow extra columns
    model_config = ConfigDict(extra="allow")


class Manifest(BaseTabular):
    """A dataset's manifest."""

    # column names
    col_participant_id = "participant_id"
    col_visit_id = "visit_id"
    col_session_id = "session_id"
    col_datatype = "datatype"

    index_cols = [col_participant_id, col_visit_id]

    # set the model
    model = ManifestModel

    _metadata = BaseTabular._metadata + [
        "col_participant_id",
        "col_visit_id",
        "col_session_id",
        "col_datatype",
        "index_cols",
        "model",
    ]

    @classmethod
    def load(
        cls, *args, session_ids=None, visit_ids=None, validate=True, **kwargs
    ) -> Self:
        """Load the manifest."""
        manifest = super().load(*args, validate=validate, **kwargs)
        manifest.session_ids = session_ids
        manifest.visit_ids = visit_ids
        return manifest

    def __init__(self, *args, session_ids=None, visit_ids=None, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.session_ids = session_ids
        self.visit_ids = visit_ids

    def validate(self, *args, **kwargs) -> Self:
        """Validate the manifest."""
        manifest = super().validate(*args, **kwargs)
        if self.session_ids is not None:
            self._check_values(self.col_session_id, self.session_ids)
        if self.visit_ids is not None:
            self._check_values(self.col_visit_id, self.visit_ids)
        return manifest

    def _check_values(self, col, allowed_values) -> Self:
        """Check that the column values are in the allowed values."""
        invalid_values = set(self[col]) - set(allowed_values)
        if len(invalid_values) > 0:
            raise ValueError(
                f"Invalid values for column {col}: {invalid_values}. "
                f"Expected only values from : {allowed_values}"
            )
        return self

    def get_imaging_subset(self, session_id: Optional[str] = None):
        """Get records with imaging data."""
        manifest = self[self[self.col_session_id].notna()]
        if session_id is not None:
            return manifest[manifest[self.col_session_id] == session_id]
        return manifest

    def get_participants_sessions(
        self, participant_id: Optional[str] = None, session_id: Optional[str] = None
    ):
        """Get participant IDs and session IDs."""
        if participant_id is None:
            participant_ids = set(self[self.col_participant_id])
        else:
            participant_ids = {participant_id}
        if session_id is None:
            session_ids = self[self.col_session_id]
            session_ids = set(session_ids[session_ids.notna()])
        else:
            session_ids = {session_id}

        manifest_subset = self[
            (self[self.col_participant_id].isin(participant_ids))
            & (self[self.col_session_id].isin(session_ids))
        ]

        yield from manifest_subset[
            [self.col_participant_id, self.col_session_id]
        ].itertuples(index=False)
