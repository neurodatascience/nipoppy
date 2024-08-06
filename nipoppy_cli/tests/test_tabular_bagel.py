"""Tests for the bagel."""

import pytest
from pydantic import ValidationError

from nipoppy.tabular.bagel import Bagel, BagelModel


@pytest.mark.parametrize(
    "data",
    [
        {
            Bagel.col_participant_id: "1",
            Bagel.col_bids_participant: "sub-1",
            Bagel.col_session_id: "01",
            Bagel.col_pipeline_name: "my_pipeline",
            Bagel.col_pipeline_version: "1.0",
            Bagel.col_pipeline_complete: Bagel.status_success,
        },
        {
            Bagel.col_participant_id: "2",
            Bagel.col_session_id: "02",
            Bagel.col_pipeline_name: "my_other_pipeline",
            Bagel.col_pipeline_version: "2.0",
            Bagel.col_pipeline_complete: Bagel.status_fail,
        },
    ],
)
def test_model(data):
    bagel = BagelModel(**data)
    assert set(bagel.model_fields.keys()) == {
        Bagel.col_participant_id,
        Bagel.col_bids_participant,
        Bagel.col_session_id,
        Bagel.col_pipeline_name,
        Bagel.col_pipeline_version,
        Bagel.col_pipeline_complete,
        "session",
        "pipeline_starttime",
    }


@pytest.mark.parametrize(
    "participant_id,expected_bids_id", [("01", "sub-01"), ("1", "sub-1")]
)
def test_model_bids_id(participant_id, expected_bids_id):
    model = BagelModel(
        participant_id=participant_id,
        session_id="01",
        pipeline_name="my_pipeline",
        pipeline_version="1.0",
        pipeline_complete=Bagel.status_success,
    )
    assert model.bids_participant == expected_bids_id


@pytest.mark.parametrize(
    "status",
    [
        Bagel.status_success,
        Bagel.status_fail,
        Bagel.status_incomplete,
        Bagel.status_unavailable,
    ],
)
def test_model_status(status):
    model = BagelModel(
        participant_id="1",
        session_id="01",
        pipeline_name="my_pipeline",
        pipeline_version="1.0",
        pipeline_complete=status,
    )
    assert model.pipeline_complete == status


def test_model_status_invalid():
    with pytest.raises(ValidationError):
        BagelModel(
            participant_id="1",
            session_id="01",
            pipeline_name="my_pipeline",
            pipeline_version="1.0",
            pipeline_complete="BAD_STATUS",
        )


@pytest.mark.parametrize(
    "data_orig,data_new,data_expected",
    [
        (
            [],
            [
                {
                    Bagel.col_participant_id: "01",
                    Bagel.col_session_id: "1",
                    Bagel.col_pipeline_name: "my_pipeline",
                    Bagel.col_pipeline_version: "1.0",
                    Bagel.col_pipeline_complete: Bagel.status_success,
                },
            ],
            [
                {
                    Bagel.col_participant_id: "01",
                    Bagel.col_session_id: "1",
                    Bagel.col_pipeline_name: "my_pipeline",
                    Bagel.col_pipeline_version: "1.0",
                    Bagel.col_pipeline_complete: Bagel.status_success,
                },
            ],
        ),
        (
            [
                {
                    Bagel.col_participant_id: "01",
                    Bagel.col_session_id: "1",
                    Bagel.col_pipeline_name: "my_pipeline",
                    Bagel.col_pipeline_version: "1.0",
                    Bagel.col_pipeline_complete: Bagel.status_fail,
                },
            ],
            [
                {
                    Bagel.col_participant_id: "01",
                    Bagel.col_session_id: "1",
                    Bagel.col_pipeline_name: "my_pipeline",
                    Bagel.col_pipeline_version: "1.0",
                    Bagel.col_pipeline_complete: Bagel.status_success,
                },
            ],
            [
                {
                    Bagel.col_participant_id: "01",
                    Bagel.col_session_id: "1",
                    Bagel.col_pipeline_name: "my_pipeline",
                    Bagel.col_pipeline_version: "1.0",
                    Bagel.col_pipeline_complete: Bagel.status_success,
                },
            ],
        ),
        (
            [
                {
                    Bagel.col_participant_id: "01",
                    Bagel.col_session_id: "1",
                    Bagel.col_pipeline_name: "my_pipeline",
                    Bagel.col_pipeline_version: "1.0",
                    Bagel.col_pipeline_complete: Bagel.status_fail,
                },
                {
                    Bagel.col_participant_id: "01",
                    Bagel.col_session_id: "2",
                    Bagel.col_pipeline_name: "my_pipeline",
                    Bagel.col_pipeline_version: "1.0",
                    Bagel.col_pipeline_complete: Bagel.status_unavailable,
                },
            ],
            [
                {
                    Bagel.col_participant_id: "01",
                    Bagel.col_session_id: "2",
                    Bagel.col_pipeline_name: "my_pipeline",
                    Bagel.col_pipeline_version: "1.0",
                    Bagel.col_pipeline_complete: Bagel.status_success,
                },
                {
                    Bagel.col_participant_id: "01",
                    Bagel.col_session_id: "3",
                    Bagel.col_pipeline_name: "my_pipeline",
                    Bagel.col_pipeline_version: "1.0",
                    Bagel.col_pipeline_complete: Bagel.status_success,
                },
            ],
            [
                {
                    Bagel.col_participant_id: "01",
                    Bagel.col_session_id: "1",
                    Bagel.col_pipeline_name: "my_pipeline",
                    Bagel.col_pipeline_version: "1.0",
                    Bagel.col_pipeline_complete: Bagel.status_fail,
                },
                {
                    Bagel.col_participant_id: "01",
                    Bagel.col_session_id: "2",
                    Bagel.col_pipeline_name: "my_pipeline",
                    Bagel.col_pipeline_version: "1.0",
                    Bagel.col_pipeline_complete: Bagel.status_success,
                },
                {
                    Bagel.col_participant_id: "01",
                    Bagel.col_session_id: "3",
                    Bagel.col_pipeline_name: "my_pipeline",
                    Bagel.col_pipeline_version: "1.0",
                    Bagel.col_pipeline_complete: Bagel.status_success,
                },
            ],
        ),
    ],
)
def test_add_or_update_records(data_orig, data_new, data_expected):
    bagel = Bagel(data_orig).validate()
    bagel = bagel.add_or_update_records(data_new)
    expected_bagel = Bagel(data_expected).validate()
    assert bagel.equals(expected_bagel)


@pytest.mark.parametrize(
    "data,pipeline_name,pipeline_version,participant_id,session_id,expected",
    [
        (
            [
                ["01", "1", "pipeline1", "1.0", Bagel.status_success],
                ["02", "1", "pipeline1", "1.0", Bagel.status_fail],
                ["03", "1", "pipeline1", "1.0", Bagel.status_incomplete],
                ["04", "1", "pipeline1", "1.0", Bagel.status_unavailable],
            ],
            "pipeline1",
            "1.0",
            None,
            None,
            [("01", "1")],
        ),
        (
            [
                ["S01", "BL", "pipeline1", "1.0", Bagel.status_success],
                ["S01", "BL", "pipeline1", "2.0", Bagel.status_success],
                ["S01", "BL", "pipeline2", "1.0", Bagel.status_success],
                ["S01", "BL", "pipeline2", "2.0", Bagel.status_success],
            ],
            "pipeline2",
            "2.0",
            None,
            None,
            [("S01", "BL")],
        ),
        (
            [
                ["S01", "BL", "pipeline1", "1.0", Bagel.status_success],
                ["S01", "BL", "pipeline1", "2.0", Bagel.status_success],
                ["S01", "BL", "pipeline2", "1.0", Bagel.status_success],
                ["S01", "M12", "pipeline2", "2.0", Bagel.status_success],
                ["S02", "BL", "pipeline1", "1.0", Bagel.status_success],
                ["S02", "BL", "pipeline1", "2.0", Bagel.status_success],
                ["S02", "BL", "pipeline2", "2.0", Bagel.status_success],
                ["S02", "M12", "pipeline2", "2.0", Bagel.status_success],
            ],
            "pipeline2",
            "2.0",
            "S02",
            "M12",
            [("S02", "M12")],
        ),
    ],
)
def test_get_completed_participants_sessions(
    data, pipeline_name, pipeline_version, participant_id, session_id, expected
):
    bagel = Bagel(
        data,
        columns=[
            Bagel.col_participant_id,
            Bagel.col_session_id,
            Bagel.col_pipeline_name,
            Bagel.col_pipeline_version,
            Bagel.col_pipeline_complete,
        ],
    ).validate()

    assert [
        tuple(x)
        for x in bagel.get_completed_participants_sessions(
            pipeline_name=pipeline_name,
            pipeline_version=pipeline_version,
            participant_id=participant_id,
            session_id=session_id,
        )
    ] == expected
