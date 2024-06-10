"""Tests for the parsers."""

from argparse import ArgumentParser

import pytest

from nipoppy.cli.parser import (
    add_arg_dataset_root,
    add_arg_dry_run,
    add_arg_pipeline_step,
    add_arg_simulate,
    add_arg_verbosity,
    add_args_participant_and_session,
    add_args_pipeline,
    add_subparser_bids_conversion,
    add_subparser_dicom_reorg,
    add_subparser_doughnut,
    add_subparser_init,
    add_subparser_pipeline_run,
    add_subparser_pipeline_track,
    get_global_parser,
)


@pytest.mark.parametrize("dataset_root", ["my_dataset", "dataset_dir"])
def test_add_arg_dataset_root(dataset_root: str):
    parser = ArgumentParser()
    parser = add_arg_dataset_root(parser)
    assert parser.parse_args(["--dataset-root", dataset_root])


def test_add_arg_simulate():
    parser = ArgumentParser()
    parser = add_arg_simulate(parser)
    assert parser.parse_args(["--simulate"])


@pytest.mark.parametrize(
    "args",
    [
        ["--pipeline", "my_pipeline"],
        ["--pipeline", "my_other_pipeline", "--pipeline-version", "1.0.0"],
    ],
)
def test_add_args_pipeline(args):
    parser = ArgumentParser()
    parser = add_args_pipeline(parser)
    assert parser.parse_args(args)


def test_add_arg_pipeline_step():
    parser = ArgumentParser()
    parser = add_arg_pipeline_step(parser)
    assert parser.parse_args(["--pipeline-step", "step1"])


@pytest.mark.parametrize(
    "args",
    [
        [],
        ["--participant", "1000"],
        ["--session", "1"],
        ["--participant", "sub-123", "--session", "ses-1"],
    ],
)
def test_add_args_participant_and_session(args):
    parser = ArgumentParser()
    parser = add_args_participant_and_session(parser)
    assert parser.parse_args(args)


def test_add_arg_dry_run():
    parser = ArgumentParser()
    parser = add_arg_dry_run(parser)
    assert parser.parse_args(["--dry-run"])


@pytest.mark.parametrize("verbosity", ["2", "3"])
def test_add_arg_verbosity(verbosity):
    parser = ArgumentParser()
    parser = add_arg_verbosity(parser)
    assert parser.parse_args(["--verbosity", verbosity])


@pytest.mark.parametrize("verbosity", ["4", "x"])
def test_add_arg_verbosity_invalid(verbosity):
    parser = ArgumentParser()
    parser = add_arg_verbosity(parser)
    with pytest.raises(SystemExit) as exception:
        parser.parse_args(["verbosity", verbosity])
    assert exception.value.code != 0, "Parsing of invalid argument should fail."


def test_add_subparser_init():
    parser = ArgumentParser()
    subparsers = parser.add_subparsers()
    add_subparser_init(subparsers)
    assert parser.parse_args(["init", "--dataset-root", "my_dataset"])


@pytest.mark.parametrize(
    "args",
    [
        ["--dataset-root", "my_dataset"],
        ["--dataset-root", "my_dataset", "--empty"],
        ["--dataset-root", "my_dataset", "--regenerate"],
        ["--dataset-root", "my_dataset", "--empty", "--regenerate"],
    ],
)
def test_add_subparser_doughnut(args):
    parser = ArgumentParser()
    subparsers = parser.add_subparsers()
    add_subparser_doughnut(subparsers)
    assert parser.parse_args(["doughnut"] + args)


@pytest.mark.parametrize(
    "args",
    [
        ["--dataset-root", "my_dataset"],
        ["--dataset-root", "my_dataset", "--copy-files"],
        ["--dataset-root", "my_dataset", "--check-dicoms"],
    ],
)
def test_add_subparser_dicom_reorg(args):
    parser = ArgumentParser()
    subparsers = parser.add_subparsers()
    add_subparser_dicom_reorg(subparsers)
    assert parser.parse_args(["reorg"] + args)


@pytest.mark.parametrize(
    "args",
    [
        ["--dataset-root", "my_dataset", "--pipeline", "pipeline1"],
        ["--dataset-root", "my_dataset", "--pipeline", "pipeline1", "--simulate"],
        [
            "--dataset-root",
            "my_dataset",
            "--pipeline",
            "pipeline1",
            "--pipeline-step",
            "step1",
        ],
    ],
)
def test_add_subparser_bids_conversion(args):
    parser = ArgumentParser()
    subparsers = parser.add_subparsers()
    add_subparser_bids_conversion(subparsers)
    assert parser.parse_args(["bidsify"] + args)


@pytest.mark.parametrize(
    "args",
    [
        ["--dataset-root", "my_dataset", "--pipeline", "pipeline1"],
        ["--dataset-root", "my_dataset", "--pipeline", "pipeline1", "--simulate"],
        [
            "--dataset-root",
            "my_dataset",
            "--pipeline",
            "pipeline1",
            "--pipeline-version",
            "1.2.3",
        ],
        [
            "--dataset-root",
            "my_dataset",
            "--pipeline",
            "pipeline1",
            "--pipeline-version",
            "1.2.3",
            "--pipeline-step",
            "step1",
        ],
        [
            "--dataset-root",
            "my_dataset",
            "--pipeline",
            "pipeline2",
            "--participant",
            "1000",
        ],
        [
            "--dataset-root",
            "my_dataset",
            "--pipeline",
            "pipeline2",
            "--participant",
            "1000",
            "--session",
            "BL",
        ],
    ],
)
def test_add_subparser_pipeline_run(args):
    parser = ArgumentParser()
    subparsers = parser.add_subparsers()
    add_subparser_pipeline_run(subparsers)
    assert parser.parse_args(["run"] + args)


@pytest.mark.parametrize(
    "args",
    [
        ["--dataset-root", "my_dataset", "--pipeline", "pipeline1"],
        [
            "--dataset-root",
            "my_dataset",
            "--pipeline",
            "pipeline1",
            "--pipeline-version",
            "1.2.3",
        ],
    ],
)
def test_add_subparser_pipeline_track(args):
    parser = ArgumentParser()
    subparsers = parser.add_subparsers()
    add_subparser_pipeline_track(subparsers)
    assert parser.parse_args(["track"] + args)


@pytest.mark.parametrize(
    "args",
    [
        ["-h"],
        ["init", "-h"],
        ["init", "--dataset-root", "my_dataset"],
        ["doughnut", "--dataset-root", "my_dataset", "--regenerate"],
        ["reorg", "--dataset-root", "my_dataset", "--copy-files"],
        ["bidsify", "--dataset-root", "my_dataset", "--pipeline", "a_bids_pipeline"],
        ["run", "--dataset-root", "my_dataset", "--pipeline", "a_pipeline"],
        ["track", "--dataset-root", "my_dataset", "--pipeline", "another_pipeline"],
    ],
)
def test_global_parser(args: list[str]):
    parser = get_global_parser()
    try:
        parser.parse_args(args)
    except SystemExit as exception:
        assert (
            exception.code == 0
        ), "Expect exit code of 0 if program exited while parsing."
