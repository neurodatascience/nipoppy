"""Tests for the CLI."""

from pathlib import Path

import pytest

from nipoppy.cli.run import cli

from .conftest import ATTR_TO_DPATH_MAP


def test_cli():
    with pytest.raises(SystemExit) as exception:
        cli(["nipoppy", "-h"])
    assert exception.value.code == 0


def test_cli_invalid():
    with pytest.raises(SystemExit) as exception:
        cli(["nipoppy", "--fake-arg"])
    assert exception.value.code != 0


def test_cli_init(tmp_path: Path):
    assert (
        cli(["nipoppy", "init", "--dataset-root", str(tmp_path / "my_dataset")]) is None
    )


def test_cli_doughnut(tmp_path: Path):
    dpath_root = tmp_path / "my_dataset"
    try:
        cli(["nipoppy", "doughnut", "--dataset-root", str(dpath_root)])
    except BaseException:
        pass

    # check that a logfile was created
    assert (
        len(list((dpath_root / ATTR_TO_DPATH_MAP["dpath_logs"]).glob("doughnut/*.log")))
        == 1
    )


def test_cli_dicom_reorg(tmp_path: Path):
    dpath_root = tmp_path / "my_dataset"
    try:
        cli(["nipoppy", "reorg", "--dataset-root", str(dpath_root)])
    except BaseException:
        pass

    # check that a logfile was created
    assert (
        len(
            list(
                (dpath_root / ATTR_TO_DPATH_MAP["dpath_logs"]).glob("dicom_reorg/*.log")
            )
        )
        == 1
    )


def test_cli_bids_conversion(tmp_path: Path):
    dpath_root = tmp_path / "my_dataset"
    try:
        cli(
            [
                "nipoppy",
                "bidsify",
                "--dataset-root",
                str(dpath_root),
                "--pipeline",
                "my_pipeline",
                "--pipeline-version",
                "1.0",
                "--pipeline-step",
                "step1",
            ]
        )
    except BaseException:
        pass

    # check that a logfile was created
    assert (
        len(
            list(
                (dpath_root / ATTR_TO_DPATH_MAP["dpath_logs"]).glob(
                    "bids_conversion/my_pipeline-1.0/*.log"
                )
            )
        )
        == 1
    )


def test_cli_pipeline_run(tmp_path: Path):
    dpath_root = tmp_path / "my_dataset"
    try:
        cli(
            [
                "nipoppy",
                "run",
                "--dataset-root",
                str(dpath_root),
                "--pipeline",
                "my_pipeline",
                "--pipeline-version",
                "1.0",
            ]
        )
    except BaseException:
        pass

    # check that a logfile was created
    assert (
        len(
            list(
                (dpath_root / ATTR_TO_DPATH_MAP["dpath_logs"]).glob(
                    "run/my_pipeline-1.0/*.log"
                )
            )
        )
        == 1
    )


def test_cli_pipeline_track(tmp_path: Path):
    dpath_root = tmp_path / "my_dataset"
    try:
        cli(
            [
                "nipoppy",
                "track",
                "--dataset-root",
                str(dpath_root),
                "--pipeline",
                "my_pipeline",
                "--pipeline-version",
                "1.0",
            ]
        )
    except BaseException:
        pass

    # check that a logfile was created
    assert (
        len(
            list(
                (dpath_root / ATTR_TO_DPATH_MAP["dpath_logs"]).glob(
                    "track/my_pipeline-1.0/*.log"
                )
            )
        )
        == 1
    )
