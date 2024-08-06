"""Tests for the PipelineTracker class."""

import json
import logging
from pathlib import Path

import pytest

from nipoppy.config.main import Config
from nipoppy.tabular.bagel import Bagel
from nipoppy.tabular.doughnut import Doughnut
from nipoppy.tabular.manifest import Manifest
from nipoppy.workflows.tracker import PipelineTracker

from .conftest import create_empty_dataset, get_config, prepare_dataset


@pytest.fixture(scope="function")
def tracker(tmp_path: Path):
    dpath_root = tmp_path / "my_dataset"
    pipeline_name = "test_pipeline"
    pipeline_version = "0.1.0"
    participants_and_sessions = {
        "01": ["1", "2"],
        "02": ["1", "2"],
    }

    tracker = PipelineTracker(
        dpath_root=dpath_root,
        pipeline_name=pipeline_name,
        pipeline_version=pipeline_version,
    )

    create_empty_dataset(dpath_root)

    manifest: Manifest = prepare_dataset(
        participants_and_sessions_manifest=participants_and_sessions,
        participants_and_sessions_bidsified=participants_and_sessions,
    )
    manifest.save_with_backup(tracker.layout.fpath_manifest)

    fpath_tracker_config = tmp_path / "tracker_config.json"
    tracker_config = [
        {
            "NAME": "pipeline_complete",
            "PATHS": [
                "[[NIPOPPY_PARTICIPANT_ID]]/[[NIPOPPY_BIDS_SESSION]]/results.txt",
                "file.txt",
            ],
        },
    ]
    fpath_tracker_config.write_text(json.dumps(tracker_config))

    config: Config = get_config(
        visit_ids=["1", "2"],
        proc_pipelines=[
            {
                "NAME": pipeline_name,
                "VERSION": pipeline_version,
                "TRACKER_CONFIG_FILE": fpath_tracker_config,
            },
        ],
    )
    config.save(tracker.layout.fpath_config)

    return tracker


def test_run_setup(tracker: PipelineTracker):
    tracker.run_setup()
    assert tracker.bagel.empty


def test_run_setup_existing_bagel(tracker: PipelineTracker):
    bagel = Bagel(
        data={
            Bagel.col_participant_id: ["01"],
            Bagel.col_session_id: ["1"],
            Bagel.col_pipeline_name: ["some_pipeline"],
            Bagel.col_pipeline_version: ["some_version"],
            Bagel.col_pipeline_complete: [Bagel.status_success],
        }
    ).validate()
    bagel.save_with_backup(tracker.layout.fpath_imaging_bagel)

    tracker.run_setup()

    assert tracker.bagel.equals(bagel)


@pytest.mark.parametrize(
    "relative_paths,expected_status",
    [
        (["01_ses-1.txt", "file.txt"], Bagel.status_success),
        (["01_ses-1.txt", "file.txt", "missing.txt"], Bagel.status_fail),
    ],
)
def test_check_status(tracker: PipelineTracker, relative_paths, expected_status):
    for relative_path_to_write in ["01_ses-1.txt", "file.txt"]:
        fpath = tracker.dpath_pipeline_output / relative_path_to_write
        fpath.mkdir(parents=True, exist_ok=True)
        fpath.touch()

    assert tracker.check_status(relative_paths) == expected_status


@pytest.mark.parametrize(
    "doughnut_data,participant_id,session_id,expected",
    [
        (
            [
                ["S01", "1", False],
                ["S01", "2", True],
                ["S02", "3", False],
            ],
            None,
            None,
            [("S01", "2")],
        ),
        (
            [
                ["P01", "A", False],
                ["P01", "B", True],
                ["P02", "B", True],
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
    tracker = PipelineTracker(
        dpath_root=tmp_path,
        pipeline_name="",
        pipeline_version="",
    )
    tracker.doughnut = Doughnut().add_or_update_records(
        records=[
            {
                Doughnut.col_participant_id: data[0],
                Doughnut.col_session_id: data[1],
                Doughnut.col_visit_id: data[1],
                Doughnut.col_in_bids: data[2],
                Doughnut.col_datatype: None,
                Doughnut.col_participant_dicom_dir: "",
                Doughnut.col_in_raw_imaging: False,
                Doughnut.col_in_sourcedata: False,
            }
            for data in doughnut_data
        ]
    )

    assert [
        tuple(x)
        for x in tracker.get_participants_sessions_to_run(
            participant_id=participant_id, session_id=session_id
        )
    ] == expected


@pytest.mark.parametrize(
    "participant_id,session_id,expected_status",
    [("01", "1", Bagel.status_success), ("02", "2", Bagel.status_fail)],
)
def test_run_single(
    participant_id, session_id, expected_status, tracker: PipelineTracker
):
    for relative_path_to_write in [
        "01/ses-1/results.txt",
        "file.txt",
        "02/ses-1/results.txt",
    ]:
        fpath = tracker.dpath_pipeline_output / relative_path_to_write
        fpath.mkdir(parents=True, exist_ok=True)
        fpath.touch()

    assert tracker.run_single(participant_id, session_id) == expected_status

    assert (
        tracker.bagel.set_index([Bagel.col_participant_id, Bagel.col_session_id])
        .loc[:, Bagel.col_pipeline_complete]
        .item()
    ) == expected_status


def test_run_single_multiple_configs(
    tracker: PipelineTracker, caplog: pytest.LogCaptureFixture
):
    tracker_configs = [
        {"NAME": "tracker1", "PATHS": ["path1"]},
        {"NAME": "tracker2", "PATHS": ["path2"]},
    ]
    tracker.pipeline_config.TRACKER_CONFIG_FILE.write_text(json.dumps(tracker_configs))
    tracker.run_single("01", "1")

    assert any(
        [
            record.levelno == logging.WARNING
            and "Currently only one config is supported" in record.message
            for record in caplog.records
        ]
    )


def test_run_single_no_config(tracker: PipelineTracker):
    tracker.pipeline_config.TRACKER_CONFIG_FILE = None
    with pytest.raises(ValueError, match="No tracker config file specified for"):
        tracker.run_single("01", "1")


@pytest.mark.parametrize(
    "bagel",
    [
        Bagel(),
        Bagel(
            data={
                Bagel.col_participant_id: ["01"],
                Bagel.col_session_id: ["1"],
                Bagel.col_pipeline_name: ["some_pipeline"],
                Bagel.col_pipeline_version: ["some_version"],
                Bagel.col_pipeline_complete: [Bagel.status_success],
            }
        ).validate(),
    ],
)
def test_run_cleanup(tracker: PipelineTracker, bagel: Bagel):
    tracker.bagel = bagel
    tracker.run_cleanup()

    assert tracker.layout.fpath_imaging_bagel.exists()
    assert Bagel.load(tracker.layout.fpath_imaging_bagel).equals(bagel)


def test_run_no_create_work_directory(tracker: PipelineTracker):
    tracker.run()
    assert not tracker.dpath_pipeline_work.exists()


def test_run_no_rm_work_directory(tracker: PipelineTracker):
    tracker.dpath_pipeline_work.mkdir(parents=True)
    tracker.run()
    assert tracker.dpath_pipeline_work.exists()
