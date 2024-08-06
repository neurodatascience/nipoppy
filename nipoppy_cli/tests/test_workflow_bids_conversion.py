"""Tests for BidsConversionWorkflow."""

from pathlib import Path

import pytest

from nipoppy.config.main import Config
from nipoppy.tabular.doughnut import Doughnut
from nipoppy.workflows.bids_conversion import BidsConversionRunner

from .conftest import create_empty_dataset, get_config


@pytest.fixture
def config() -> Config:
    return get_config(
        bids_pipelines=[
            {
                "NAME": "heudiconv",
                "VERSION": "0.12.2",
                "STEPS": [
                    {"NAME": "prepare"},
                    {"NAME": "convert", "UPDATE_DOUGHNUT": True},
                ],
            },
            {
                "NAME": "dcm2bids",
                "VERSION": "3.1.0",
                "STEPS": [
                    {"NAME": "prepare"},
                    {"NAME": "convert", "UPDATE_DOUGHNUT": True},
                ],
            },
        ]
    )


def test_setup(config: Config, tmp_path: Path):
    workflow = BidsConversionRunner(
        dpath_root=tmp_path / "my_dataset",
        pipeline_name="heudiconv",
        pipeline_version="0.12.2",
        pipeline_step="prepare",
    )
    create_empty_dataset(workflow.dpath_root)
    config.save(workflow.layout.fpath_config)
    workflow.run_setup()
    assert not workflow.dpath_pipeline.exists()


@pytest.mark.parametrize(
    "doughnut",
    [
        Doughnut(),
        Doughnut(
            data={
                Doughnut.col_participant_id: ["01"],
                Doughnut.col_visit_id: ["1"],
                Doughnut.col_session_id: ["1"],
                Doughnut.col_datatype: "['anat']",
                Doughnut.col_participant_dicom_dir: ["01"],
                Doughnut.col_in_raw_imaging: [True],
                Doughnut.col_in_sourcedata: [True],
                Doughnut.col_in_bids: [True],
            }
        ).validate(),
    ],
)
def test_cleanup(doughnut: Doughnut, config: Config, tmp_path: Path):
    workflow = BidsConversionRunner(
        dpath_root=tmp_path / "my_dataset",
        pipeline_name="heudiconv",
        pipeline_version="0.12.2",
        pipeline_step="convert",
    )
    workflow.doughnut = doughnut
    config.save(workflow.layout.fpath_config)

    workflow.run_cleanup()

    assert workflow.layout.fpath_doughnut.exists()
    assert Doughnut.load(workflow.layout.fpath_doughnut).equals(doughnut)


def test_cleanup_simulate(tmp_path: Path, config: Config):
    workflow = BidsConversionRunner(
        dpath_root=tmp_path / "my_dataset",
        pipeline_name="heudiconv",
        pipeline_version="0.12.2",
        pipeline_step="convert",
        simulate=True,
    )
    workflow.doughnut = Doughnut()
    config.save(workflow.layout.fpath_config)

    workflow.run_cleanup()

    assert not workflow.layout.fpath_doughnut.exists()


def test_cleanup_no_doughnut_update(config: Config, tmp_path: Path):
    workflow = BidsConversionRunner(
        dpath_root=tmp_path / "my_dataset",
        pipeline_name="heudiconv",
        pipeline_version="0.12.2",
        pipeline_step="prepare",
    )
    workflow.doughnut = Doughnut()
    config.save(workflow.layout.fpath_config)

    print(config.get_pipeline_config("heudiconv", "0.12.2"))

    workflow.run_cleanup()

    assert not workflow.layout.fpath_doughnut.exists()


@pytest.mark.parametrize(
    "doughnut_data,participant_id,session_id,expected",
    [
        (
            [
                ["S01", "1", True, False],
                ["S01", "2", True, True],
                ["S02", "3", False, False],
            ],
            None,
            None,
            [("S01", "1")],
        ),
        (
            [
                ["P01", "A", True, False],
                ["P01", "B", True, False],
                ["P02", "B", True, False],
            ],
            "P01",
            "B",
            [("P01", "B")],
        ),
    ],
)
def test_get_participants_sessions_to_run(
    doughnut_data, participant_id, session_id, expected, tmp_path: Path
):
    workflow = BidsConversionRunner(
        dpath_root=tmp_path / "my_dataset",
        pipeline_name="heudiconv",
        pipeline_version="0.12.2",
        pipeline_step="prepare",
    )
    workflow.doughnut = Doughnut().add_or_update_records(
        records=[
            {
                Doughnut.col_participant_id: data[0],
                Doughnut.col_session_id: data[1],
                Doughnut.col_in_sourcedata: data[2],
                Doughnut.col_in_bids: data[3],
                Doughnut.col_visit_id: data[1],
                Doughnut.col_datatype: None,
                Doughnut.col_participant_dicom_dir: "",
                Doughnut.col_in_raw_imaging: False,
            }
            for data in doughnut_data
        ]
    )
    assert [
        tuple(x)
        for x in workflow.get_participants_sessions_to_run(
            participant_id=participant_id, session_id=session_id
        )
    ] == expected
