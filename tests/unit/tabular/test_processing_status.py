"""Tests for the processing status table."""

import pytest

from nipoppy.exceptions import TabularError
from nipoppy.tabular.processing_status import (
    ProcessingStatusModel,
    ProcessingStatusTable,
)
from tests.conftest import DPATH_TEST_DATA


@pytest.mark.parametrize(
    "data",
    [
        {
            ProcessingStatusTable.col_participant_id: "1",
            ProcessingStatusTable.col_bids_participant_id: "sub-1",
            ProcessingStatusTable.col_session_id: "01",
            ProcessingStatusTable.col_pipeline_name: "my_pipeline",
            ProcessingStatusTable.col_pipeline_version: "1.0",
            ProcessingStatusTable.col_pipeline_step: "a_step",
            ProcessingStatusTable.col_status: ProcessingStatusTable.status_success,
        },
        {
            ProcessingStatusTable.col_participant_id: "2",
            ProcessingStatusTable.col_session_id: "02",
            ProcessingStatusTable.col_pipeline_name: "my_other_pipeline",
            ProcessingStatusTable.col_pipeline_version: "2.0",
            ProcessingStatusTable.col_pipeline_step: "another_step",
            ProcessingStatusTable.col_status: ProcessingStatusTable.status_fail,
        },
    ],
)
def test_model(data):
    processing_status_record = ProcessingStatusModel(**data)
    assert set(processing_status_record.model_dump().keys()) == {
        ProcessingStatusTable.col_participant_id,
        ProcessingStatusTable.col_bids_participant_id,
        ProcessingStatusTable.col_session_id,
        ProcessingStatusTable.col_pipeline_name,
        ProcessingStatusTable.col_pipeline_version,
        ProcessingStatusTable.col_pipeline_step,
        ProcessingStatusTable.col_status,
        ProcessingStatusTable.col_bids_session_id,
    }


@pytest.mark.parametrize(
    "participant_id,expected_bids_id", [("01", "sub-01"), ("1", "sub-1")]
)
def test_model_bids_id(participant_id, expected_bids_id):
    model = ProcessingStatusModel(
        participant_id=participant_id,
        session_id="01",
        pipeline_name="my_pipeline",
        pipeline_version="1.0",
        pipeline_step="step1",
        status=ProcessingStatusTable.status_success,
    )
    assert model.bids_participant_id == expected_bids_id


@pytest.mark.parametrize(
    "status",
    [
        ProcessingStatusTable.status_success,
        ProcessingStatusTable.status_fail,
        ProcessingStatusTable.status_incomplete,
        ProcessingStatusTable.status_unavailable,
    ],
)
def test_model_status(status):
    model = ProcessingStatusModel(
        participant_id="1",
        session_id="01",
        pipeline_name="my_pipeline",
        pipeline_version="1.0",
        pipeline_step="step1",
        status=status,
    )
    assert model.status == status


@pytest.mark.parametrize("status", ["BAD_STATUS", "", "success"])
def test_model_status_invalid(status):
    with pytest.raises(TabularError):
        ProcessingStatusModel(
            participant_id="1",
            session_id="01",
            pipeline_name="my_pipeline",
            pipeline_version="1.0",
            pipeline_step="step1",
            status=status,
        )


@pytest.mark.parametrize(
    "data_orig,data_new,data_expected",
    [
        (
            [],
            [
                {
                    ProcessingStatusTable.col_participant_id: "01",
                    ProcessingStatusTable.col_session_id: "1",
                    ProcessingStatusTable.col_pipeline_name: "my_pipeline",
                    ProcessingStatusTable.col_pipeline_version: "1.0",
                    ProcessingStatusTable.col_pipeline_step: "step1",
                    ProcessingStatusTable.col_status: ProcessingStatusTable.status_success,  # noqa E501
                },
            ],
            [
                {
                    ProcessingStatusTable.col_participant_id: "01",
                    ProcessingStatusTable.col_session_id: "1",
                    ProcessingStatusTable.col_pipeline_name: "my_pipeline",
                    ProcessingStatusTable.col_pipeline_version: "1.0",
                    ProcessingStatusTable.col_pipeline_step: "step1",
                    ProcessingStatusTable.col_status: ProcessingStatusTable.status_success,  # noqa E501
                },
            ],
        ),
        (
            [
                {
                    ProcessingStatusTable.col_participant_id: "01",
                    ProcessingStatusTable.col_session_id: "1",
                    ProcessingStatusTable.col_pipeline_name: "my_pipeline",
                    ProcessingStatusTable.col_pipeline_version: "1.0",
                    ProcessingStatusTable.col_pipeline_step: "step1",
                    ProcessingStatusTable.col_status: ProcessingStatusTable.status_fail,
                },
            ],
            [
                {
                    ProcessingStatusTable.col_participant_id: "01",
                    ProcessingStatusTable.col_session_id: "1",
                    ProcessingStatusTable.col_pipeline_name: "my_pipeline",
                    ProcessingStatusTable.col_pipeline_version: "1.0",
                    ProcessingStatusTable.col_pipeline_step: "step1",
                    ProcessingStatusTable.col_status: ProcessingStatusTable.status_success,  # noqa E501
                },
            ],
            [
                {
                    ProcessingStatusTable.col_participant_id: "01",
                    ProcessingStatusTable.col_session_id: "1",
                    ProcessingStatusTable.col_pipeline_name: "my_pipeline",
                    ProcessingStatusTable.col_pipeline_version: "1.0",
                    ProcessingStatusTable.col_pipeline_step: "step1",
                    ProcessingStatusTable.col_status: ProcessingStatusTable.status_success,  # noqa E501
                },
            ],
        ),
        (
            [
                {
                    ProcessingStatusTable.col_participant_id: "01",
                    ProcessingStatusTable.col_session_id: "1",
                    ProcessingStatusTable.col_pipeline_name: "my_pipeline",
                    ProcessingStatusTable.col_pipeline_version: "1.0",
                    ProcessingStatusTable.col_pipeline_step: "step1",
                    ProcessingStatusTable.col_status: ProcessingStatusTable.status_fail,
                },
                {
                    ProcessingStatusTable.col_participant_id: "01",
                    ProcessingStatusTable.col_session_id: "2",
                    ProcessingStatusTable.col_pipeline_name: "my_pipeline",
                    ProcessingStatusTable.col_pipeline_version: "1.0",
                    ProcessingStatusTable.col_pipeline_step: "step1",
                    ProcessingStatusTable.col_status: ProcessingStatusTable.status_unavailable,  # noqa E501
                },
            ],
            [
                {
                    ProcessingStatusTable.col_participant_id: "01",
                    ProcessingStatusTable.col_session_id: "2",
                    ProcessingStatusTable.col_pipeline_name: "my_pipeline",
                    ProcessingStatusTable.col_pipeline_version: "1.0",
                    ProcessingStatusTable.col_pipeline_step: "step1",
                    ProcessingStatusTable.col_status: ProcessingStatusTable.status_success,  # noqa E501
                },
                {
                    ProcessingStatusTable.col_participant_id: "01",
                    ProcessingStatusTable.col_session_id: "3",
                    ProcessingStatusTable.col_pipeline_name: "my_pipeline",
                    ProcessingStatusTable.col_pipeline_version: "1.0",
                    ProcessingStatusTable.col_pipeline_step: "step1",
                    ProcessingStatusTable.col_status: ProcessingStatusTable.status_success,  # noqa E501
                },
            ],
            [
                {
                    ProcessingStatusTable.col_participant_id: "01",
                    ProcessingStatusTable.col_session_id: "1",
                    ProcessingStatusTable.col_pipeline_name: "my_pipeline",
                    ProcessingStatusTable.col_pipeline_version: "1.0",
                    ProcessingStatusTable.col_pipeline_step: "step1",
                    ProcessingStatusTable.col_status: ProcessingStatusTable.status_fail,
                },
                {
                    ProcessingStatusTable.col_participant_id: "01",
                    ProcessingStatusTable.col_session_id: "2",
                    ProcessingStatusTable.col_pipeline_name: "my_pipeline",
                    ProcessingStatusTable.col_pipeline_version: "1.0",
                    ProcessingStatusTable.col_pipeline_step: "step1",
                    ProcessingStatusTable.col_status: ProcessingStatusTable.status_success,  # noqa E501
                },
                {
                    ProcessingStatusTable.col_participant_id: "01",
                    ProcessingStatusTable.col_session_id: "3",
                    ProcessingStatusTable.col_pipeline_name: "my_pipeline",
                    ProcessingStatusTable.col_pipeline_version: "1.0",
                    ProcessingStatusTable.col_pipeline_step: "step1",
                    ProcessingStatusTable.col_status: ProcessingStatusTable.status_success,  # noqa E501
                },
            ],
        ),
    ],
)
def test_add_or_update_records(data_orig, data_new, data_expected):
    processing_status_table = ProcessingStatusTable(data_orig).validate()
    processing_status_table = processing_status_table.add_or_update_records(data_new)
    expected_table = ProcessingStatusTable(data_expected).validate()
    assert processing_status_table.equals(expected_table)


@pytest.mark.parametrize(
    "data,pipeline_name,pipeline_version,pipeline_step,participant_id,session_id,expected",  # noqa E501
    [
        (
            [
                [
                    "01",
                    "1",
                    "pipeline1",
                    "1.0",
                    "step1",
                    ProcessingStatusTable.status_success,
                ],
                [
                    "02",
                    "1",
                    "pipeline1",
                    "1.0",
                    "step1",
                    ProcessingStatusTable.status_fail,
                ],
                [
                    "03",
                    "1",
                    "pipeline1",
                    "1.0",
                    "step1",
                    ProcessingStatusTable.status_incomplete,
                ],
                [
                    "04",
                    "1",
                    "pipeline1",
                    "1.0",
                    "step1",
                    ProcessingStatusTable.status_unavailable,
                ],
            ],
            "pipeline1",
            "1.0",
            "step1",
            None,
            None,
            [("01", "1")],
        ),
        (
            [
                [
                    "S01",
                    "BL",
                    "pipeline1",
                    "1.0",
                    "step1",
                    ProcessingStatusTable.status_success,
                ],
                [
                    "S01",
                    "BL",
                    "pipeline1",
                    "2.0",
                    "step1",
                    ProcessingStatusTable.status_success,
                ],
                [
                    "S01",
                    "BL",
                    "pipeline2",
                    "1.0",
                    "step1",
                    ProcessingStatusTable.status_success,
                ],
                [
                    "S01",
                    "BL",
                    "pipeline2",
                    "2.0",
                    "step1",
                    ProcessingStatusTable.status_success,
                ],
            ],
            "pipeline2",
            "2.0",
            "step1",
            None,
            None,
            [("S01", "BL")],
        ),
        (
            [
                [
                    "S01",
                    "BL",
                    "pipeline1",
                    "1.0",
                    "step1",
                    ProcessingStatusTable.status_success,
                ],
                [
                    "S01",
                    "BL",
                    "pipeline1",
                    "2.0",
                    "step1",
                    ProcessingStatusTable.status_success,
                ],
                [
                    "S01",
                    "BL",
                    "pipeline2",
                    "1.0",
                    "step1",
                    ProcessingStatusTable.status_success,
                ],
                [
                    "S01",
                    "M12",
                    "pipeline2",
                    "2.0",
                    "step1",
                    ProcessingStatusTable.status_success,
                ],
                [
                    "S02",
                    "BL",
                    "pipeline1",
                    "1.0",
                    "step1",
                    ProcessingStatusTable.status_success,
                ],
                [
                    "S02",
                    "BL",
                    "pipeline1",
                    "2.0",
                    "step1",
                    ProcessingStatusTable.status_success,
                ],
                [
                    "S02",
                    "BL",
                    "pipeline2",
                    "2.0",
                    "step1",
                    ProcessingStatusTable.status_success,
                ],
                [
                    "S02",
                    "M12",
                    "pipeline2",
                    "2.0",
                    "step1",
                    ProcessingStatusTable.status_success,
                ],
            ],
            "pipeline2",
            "2.0",
            "step1",
            "S02",
            "M12",
            [("S02", "M12")],
        ),
    ],
)
def test_get_completed_participants_sessions(
    data,
    pipeline_name,
    pipeline_version,
    pipeline_step,
    participant_id,
    session_id,
    expected,
):
    processing_status_table = ProcessingStatusTable(
        data,
        columns=[
            ProcessingStatusTable.col_participant_id,
            ProcessingStatusTable.col_session_id,
            ProcessingStatusTable.col_pipeline_name,
            ProcessingStatusTable.col_pipeline_version,
            ProcessingStatusTable.col_pipeline_step,
            ProcessingStatusTable.col_status,
        ],
    ).validate()

    assert [
        tuple(x)
        for x in processing_status_table.get_completed_participants_sessions(
            pipeline_name=pipeline_name,
            pipeline_version=pipeline_version,
            pipeline_step=pipeline_step,
            participant_id=participant_id,
            session_id=session_id,
        )
    ] == expected


@pytest.mark.parametrize(
    "fpath",
    [
        DPATH_TEST_DATA / "processing_status1.tsv",
        DPATH_TEST_DATA / "processing_status2.tsv",
    ],
)
def test_load(fpath):
    processing_status_table = ProcessingStatusTable.load(fpath)
    assert isinstance(processing_status_table, ProcessingStatusTable)


@pytest.mark.parametrize(
    "fname",
    [
        "processing_status_invalid1.tsv",
        "processing_status_invalid2.tsv",
    ],
)
def test_load_invalid(fname):
    with pytest.raises(TabularError):
        ProcessingStatusTable.load(DPATH_TEST_DATA / fname)
