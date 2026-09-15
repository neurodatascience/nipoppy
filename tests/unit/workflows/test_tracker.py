"""Tests for the PipelineTracker class."""

import json
import logging
from pathlib import Path

import pandas as pd
import pytest
import pytest_mock

from nipoppy.config.pipeline_step import AnalysisLevelType
from nipoppy.env import DEFAULT_PIPELINE_STEP_NAME
from nipoppy.tabular.curation_status import CurationStatusTable
from nipoppy.tabular.manifest import Manifest
from nipoppy.tabular.processing_status import ProcessingStatusTable
from nipoppy.workflows.processing_runner import ProcessingRunner
from nipoppy.workflows.tracker import PipelineTracker
from tests.conftest import (
    create_empty_dataset,
    create_pipeline_config_files,
    get_config,
    prepare_dataset,
)


@pytest.fixture(scope="function")
def tracker(tmp_path: Path):
    participants_and_sessions = {
        "01": ["1", "2"],
        "02": ["1", "2"],
    }

    tracker = PipelineTracker(
        dpath_root=tmp_path / "my_dataset",
        pipeline_name="test_pipeline",
        pipeline_version="0.1.0",
        pipeline_step=DEFAULT_PIPELINE_STEP_NAME,
    )

    create_empty_dataset(tracker.dpath_root)

    manifest: Manifest = prepare_dataset(
        participants_and_sessions_manifest=participants_and_sessions,
        participants_and_sessions_bidsified=participants_and_sessions,
    )
    manifest.save_with_backup(tracker.study.layout.fpath_manifest)

    tracker.study.config = get_config()

    fname_tracker_config = "tracker_config.json"
    create_pipeline_config_files(
        tracker.study.layout.dpath_pipelines,
        processing_pipelines=[
            {
                "NAME": tracker.pipeline_name,
                "VERSION": tracker.pipeline_version,
                "STEPS": [
                    {
                        "NAME": tracker.pipeline_step,
                        "TRACKER_CONFIG_FILE": fname_tracker_config,
                    }
                ],
            },
        ],
    )
    tracker_config = {
        "PATHS": [
            "[[NIPOPPY_PARTICIPANT_ID]]/[[NIPOPPY_BIDS_SESSION_ID]]/results.txt",
            "file.txt",
        ],
        "PARTICIPANT_SESSION_DIR": "[[NIPOPPY_PARTICIPANT_ID]]/[[NIPOPPY_BIDS_SESSION_ID]]",
    }

    (tracker.dpath_pipeline_bundle / fname_tracker_config).write_text(
        json.dumps(tracker_config)
    )

    return tracker


@pytest.mark.parametrize(
    "analysis_level",
    tuple(AnalysisLevelType),
)
def test_apply_analysis_level_success(analysis_level):
    participants_sessions = [("S01", "BL"), ("S01", "FU"), ("S02", "BL"), ("S02", "FU")]
    assert (
        PipelineTracker.apply_analysis_level(participants_sessions, analysis_level)
        == participants_sessions
    )


def test_run_setup(tracker: PipelineTracker):
    tracker.run_setup()
    assert tracker.processing_status_table.empty
    assert not tracker.dpath_pipeline.exists(), "Tracker should not create directory"


def test_run_setup_existing_processing_status_file(tracker: PipelineTracker):
    processing_status_table = ProcessingStatusTable(
        data={
            ProcessingStatusTable.col_participant_id: ["01"],
            ProcessingStatusTable.col_session_id: ["1"],
            ProcessingStatusTable.col_pipeline_name: ["some_pipeline"],
            ProcessingStatusTable.col_pipeline_version: ["some_version"],
            ProcessingStatusTable.col_pipeline_step: ["some_step"],
            ProcessingStatusTable.col_status: [ProcessingStatusTable.status_success],
        }
    ).validate()
    processing_status_table.save_with_backup(
        tracker.study.layout.fpath_processing_status
    )

    tracker.run_setup()

    assert tracker.processing_status_table.equals(processing_status_table)


@pytest.mark.no_xdist
def test_run_setup_existing_bad_processing_status_file(
    tracker: PipelineTracker, caplog: pytest.LogCaptureFixture
):
    # processing status file with wrong columns
    bad_processing_status_table = pd.DataFrame([{"col1": "val1"}])
    bad_processing_status_table.to_csv(
        tracker.study.layout.fpath_processing_status, index=False
    )

    tracker.run_setup()

    assert any(
        [
            record.levelno == logging.WARNING
            and "Failed to load existing processing status file at " in record.message
            for record in caplog.records
        ]
    )
    assert tracker.processing_status_table.empty


@pytest.mark.parametrize(
    "relative_paths,expected_status",
    [
        (
            ["dirA/01_ses-1.txt", "dirA/dirB/file.txt"],
            ProcessingStatusTable.status_success,
        ),
        (["**/*.txt"], ProcessingStatusTable.status_success),
        (["*file.txt"], ProcessingStatusTable.status_fail),
        (
            ["dirA/01_ses-1.txt", "dirA/dirB/file.txt", "missing.txt"],
            ProcessingStatusTable.status_fail,
        ),
    ],
)
def test_check_status(tracker: PipelineTracker, relative_paths, expected_status):
    for relative_path_to_write in ["dirA/01_ses-1.txt", "dirA/dirB/file.txt"]:
        fpath = tracker.dpath_pipeline_output / relative_path_to_write
        fpath.parent.mkdir(parents=True, exist_ok=True)
        fpath.touch()

    assert tracker.check_status(relative_paths) == expected_status


@pytest.mark.ai_generated
@pytest.mark.parametrize(
    "relative_paths,broken_symlinks,regular_files,expected_status",
    [
        # One broken symlink + one regular file → UNAVAILABLE
        (
            ["dirA/01_ses-1.txt", "dirA/dirB/file.txt"],
            ["dirA/01_ses-1.txt"],
            ["dirA/dirB/file.txt"],
            ProcessingStatusTable.status_unavailable,
        ),
        # All broken symlinks → UNAVAILABLE
        (
            ["dirA/01_ses-1.txt", "dirA/dirB/file.txt"],
            ["dirA/01_ses-1.txt", "dirA/dirB/file.txt"],
            [],
            ProcessingStatusTable.status_unavailable,
        ),
        # Broken symlink + missing file → FAIL (FAIL takes priority)
        (
            ["dirA/01_ses-1.txt", "dirA/dirB/file.txt", "missing.txt"],
            ["dirA/01_ses-1.txt"],
            ["dirA/dirB/file.txt"],
            ProcessingStatusTable.status_fail,
        ),
    ],
)
def test_check_status_broken_symlinks(
    tracker: PipelineTracker,
    relative_paths,
    broken_symlinks,
    regular_files,
    expected_status,
):
    """Test that broken symlinks (git-annex) yield UNAVAILABLE status."""
    # Create regular files
    for relative_path in regular_files:
        fpath = tracker.dpath_pipeline_output / relative_path
        fpath.parent.mkdir(parents=True, exist_ok=True)
        fpath.touch()

    # Create broken symlinks (simulating git-annex without content)
    for relative_path in broken_symlinks:
        fpath = tracker.dpath_pipeline_output / relative_path
        fpath.parent.mkdir(parents=True, exist_ok=True)
        fpath.symlink_to("/nonexistent-annex-target")

    assert tracker.check_status(relative_paths) == expected_status


@pytest.mark.parametrize(
    "relative_paths,relative_dpath_to_tar,expected_status",
    [
        (
            ["dirA/01_ses-1.txt", "dirA/dirB/file.txt"],
            "dirA",
            ProcessingStatusTable.status_success,
        ),
        (
            ["dirA/*.txt", "dirA/dirB/file.txt"],
            "dirA",
            ProcessingStatusTable.status_success,
        ),
        (["**/*.txt"], "dirA", ProcessingStatusTable.status_success),
        # # FAILING, see note in check_status
        # (["*file.txt"], "dirA", ProcessingStatus.status_fail),
        (
            ["dirA/01_ses-1.txt", "dirA/dirB/file.txt", "missing.txt"],
            "dirA",
            ProcessingStatusTable.status_fail,
        ),
        (
            ["dirA/01_ses-1.txt", "dirA/dirB/file.txt"],
            "dirA/dirB",
            ProcessingStatusTable.status_success,
        ),
    ],
)
def test_check_status_with_tarball(
    tracker: PipelineTracker,
    relative_paths: list[str],
    relative_dpath_to_tar: str,
    expected_status,
):
    for relative_path_to_write in ["dirA/01_ses-1.txt", "dirA/dirB/file.txt"]:
        fpath = tracker.dpath_pipeline_output / relative_path_to_write
        fpath.parent.mkdir(parents=True, exist_ok=True)
        fpath.touch()

    # use PipelineRunner to tar the directory
    dpath_to_tar = tracker.dpath_pipeline_output / relative_dpath_to_tar
    ProcessingRunner(
        tracker.dpath_root, tracker.pipeline_name, tracker.pipeline_version
    ).tar_directory(dpath_to_tar)

    assert not dpath_to_tar.exists()
    assert (
        tracker.check_status(relative_paths, relative_dpath_to_tar) == expected_status
    )


@pytest.mark.parametrize(
    "curation_status_data,participant_id,session_id,expected",
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
    curation_status_data, participant_id, session_id, expected, tmp_path: Path
):
    tracker = PipelineTracker(
        dpath_root=tmp_path,
        pipeline_name="",
        pipeline_version="",
    )
    tracker.curation_status_table = CurationStatusTable().add_or_update_records(
        records=[
            {
                CurationStatusTable.col_participant_id: data[0],
                CurationStatusTable.col_session_id: data[1],
                CurationStatusTable.col_visit_id: data[1],
                CurationStatusTable.col_in_bids: data[2],
                CurationStatusTable.col_datatype: None,
                CurationStatusTable.col_participant_dicom_dir: "",
                CurationStatusTable.col_in_pre_reorg: False,
                CurationStatusTable.col_in_post_reorg: False,
            }
            for data in curation_status_data
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
    [
        ("01", "1", ProcessingStatusTable.status_success),
        ("02", "2", ProcessingStatusTable.status_fail),
    ],
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
        fpath.parent.mkdir(parents=True, exist_ok=True)
        fpath.touch()

    for relative_dpath_to_tar in ["01/ses-1", "02/ses-1"]:
        dpath_to_tar = tracker.dpath_pipeline_output / relative_dpath_to_tar
        ProcessingRunner(
            tracker.dpath_root, tracker.pipeline_name, tracker.pipeline_version
        ).tar_directory(dpath_to_tar)

    assert not dpath_to_tar.exists()
    assert (
        tracker.run_single(participant_id, session_id)[ProcessingStatusTable.col_status]
        == expected_status
    )


def test_run_single_no_config(tracker: PipelineTracker):
    tracker.pipeline_config.STEPS[0].TRACKER_CONFIG_FILE = None
    with pytest.raises(ValueError, match="No tracker config file specified for"):
        tracker.run_single("01", "1")


@pytest.mark.parametrize(
    "records,expected_processing_status_table",
    [
        ([], ProcessingStatusTable()),
        (
            [
                {
                    ProcessingStatusTable.col_participant_id: "01",
                    ProcessingStatusTable.col_session_id: "1",
                    ProcessingStatusTable.col_pipeline_name: "some_pipeline",
                    ProcessingStatusTable.col_pipeline_version: "some_version",
                    ProcessingStatusTable.col_pipeline_step: "some_step",
                    ProcessingStatusTable.col_status: ProcessingStatusTable.status_success,  # noqa: E501
                }
            ],
            ProcessingStatusTable(
                data={
                    ProcessingStatusTable.col_participant_id: ["01"],
                    ProcessingStatusTable.col_session_id: ["1"],
                    ProcessingStatusTable.col_pipeline_name: ["some_pipeline"],
                    ProcessingStatusTable.col_pipeline_version: ["some_version"],
                    ProcessingStatusTable.col_pipeline_step: ["some_step"],
                    ProcessingStatusTable.col_status: [
                        ProcessingStatusTable.status_success
                    ],
                }
            ).validate(),
        ),
    ],
)
def test_update_status_file(
    tracker: PipelineTracker,
    records,
    expected_processing_status_table: ProcessingStatusTable,
):
    tracker.run_single_results = records
    tracker._update_status_file()

    assert tracker.study.layout.fpath_processing_status.exists()
    assert ProcessingStatusTable.load(
        tracker.study.layout.fpath_processing_status
    ).equals(expected_processing_status_table)


def test_run_main(tracker: PipelineTracker, mocker: pytest_mock.MockFixture):
    mocked_update_status_file = mocker.patch.object(tracker, "_update_status_file")
    tracker.run_main()
    mocked_update_status_file.assert_called_once()


def test_run_no_create_work_directory(tracker: PipelineTracker):
    tracker.run()
    assert not tracker.dpath_pipeline_work.exists()


def test_run_no_rm_work_directory(tracker: PipelineTracker):
    tracker.dpath_pipeline_work.mkdir(parents=True)
    tracker.run()
    assert tracker.dpath_pipeline_work.exists()
