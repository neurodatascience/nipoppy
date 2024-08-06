"""Tests for BasePipelineWorkflow."""

import json
import logging
import re
from pathlib import Path
from typing import Optional

import pytest
from fids import fids

from nipoppy.config.boutiques import BoutiquesConfig
from nipoppy.config.pipeline import ProcPipelineConfig
from nipoppy.config.pipeline_step import ProcPipelineStepConfig
from nipoppy.env import StrOrPathLike
from nipoppy.workflows.pipeline import BasePipelineWorkflow

from .conftest import datetime_fixture  # noqa F401
from .conftest import create_empty_dataset, get_config, prepare_dataset


class PipelineWorkflow(BasePipelineWorkflow):
    def __init__(
        self,
        dpath_root: StrOrPathLike,
        pipeline_name: str,
        pipeline_version: Optional[str] = None,
        pipeline_step: Optional[str] = None,
        participant_id: str = None,
        session_id: str = None,
        fpath_layout: Optional[StrOrPathLike] = None,
        logger: Optional[logging.Logger] = None,
        dry_run: bool = False,
    ):
        self._n_runs = 0
        self._n_errors = 0
        super().__init__(
            dpath_root=dpath_root,
            name="test",
            pipeline_name=pipeline_name,
            pipeline_version=pipeline_version,
            pipeline_step=pipeline_step,
            participant_id=participant_id,
            session_id=session_id,
            fpath_layout=fpath_layout,
            logger=logger,
            dry_run=dry_run,
        )

    def get_participants_sessions_to_run(
        self, participant_id: Optional[str], session_id: Optional[str]
    ):
        """Only run on participant_id/sessions with BIDS data."""
        return self.doughnut.get_bidsified_participants_sessions(
            participant_id=participant_id, session_id=session_id
        )

    def run_single(self, participant: str, session_id: str):
        """Run on a single participant_id/session_id."""
        self._n_runs += 1
        self.logger.info(f"Running on participant {participant}, session {session_id}")
        if participant == "FAIL":
            self._n_errors += 1
            raise RuntimeError("FAIL")


@pytest.fixture(scope="function")
def workflow(tmp_path: Path):
    workflow = PipelineWorkflow(
        dpath_root=tmp_path / "my_dataset",
        pipeline_name="my_pipeline",
        pipeline_version="1.0",
    )
    # write config
    config = get_config(
        visit_ids=["1"],
        bids_pipelines=[
            # built-in pipelines
            {
                "NAME": "heudiconv",
                "VERSION": "0.12.2",
                "STEPS": [{"NAME": "prepare"}, {"NAME": "convert"}],
            }
        ],
        proc_pipelines=[
            # built-in pipelines
            {
                "NAME": "fmriprep",
                "VERSION": "23.1.3",
                "STEPS": [{}],
            },
            # user-added pipeline
            {
                "NAME": "my_pipeline",
                "VERSION": "1.0",
                "CONTAINER_INFO": {
                    "FILE": "[[NIPOPPY_DPATH_CONTAINERS]]/my_container.sif"
                },
                "STEPS": [{}],
            },
            {
                "NAME": "my_pipeline",
                "VERSION": "2.0",
                "STEPS": [{}],
            },
        ],
    )
    config.save(workflow.layout.fpath_config)
    return workflow


@pytest.mark.parametrize(
    "args",
    [
        {
            "dpath_root": "my_dataset",
            "pipeline_name": "my_pipeline",
            "pipeline_version": "1.0",
        },
        {
            "dpath_root": "my_dataset",
            "pipeline_name": "my_other_pipeline",
            "pipeline_version": "2.0",
        },
    ],
)
def test_init(args):
    workflow = PipelineWorkflow(**args)
    assert isinstance(workflow, BasePipelineWorkflow)
    assert hasattr(workflow, "pipeline_name")
    assert hasattr(workflow, "pipeline_version")
    assert hasattr(workflow, "pipeline_step")
    assert hasattr(workflow, "participant_id")
    assert hasattr(workflow, "session_id")
    assert isinstance(workflow.dpath_pipeline, Path)
    assert isinstance(workflow.dpath_pipeline_output, Path)
    assert isinstance(workflow.dpath_pipeline_work, Path)
    assert isinstance(workflow.dpath_pipeline_bids_db, Path)


@pytest.mark.parametrize(
    "participant_id,session_id,participant_expected,session_expected",
    [
        ("01", "BL", "01", "BL"),
        ("sub-01", "ses-BL", "01", "BL"),
    ],
)
def test_init_participant_session(
    participant_id, session_id, participant_expected, session_expected
):
    workflow = PipelineWorkflow(
        dpath_root="my_dataset",
        pipeline_name="my_pipeline",
        pipeline_version="1.0",
        participant_id=participant_id,
        session_id=session_id,
    )
    assert workflow.participant_id == participant_expected
    assert workflow.session_id == session_expected


def test_pipeline_version_optional():
    workflow = PipelineWorkflow(
        dpath_root="my_dataset",
        pipeline_name="my_pipeline",
    )
    assert workflow.pipeline_version is None


def test_pipeline_config(workflow: PipelineWorkflow):
    assert isinstance(workflow.pipeline_config, ProcPipelineConfig)


def test_fpath_container(workflow: PipelineWorkflow):
    fpath_container = workflow.layout.dpath_containers / "my_container.sif"
    fpath_container.parent.mkdir(parents=True, exist_ok=True)
    fpath_container.touch()
    assert isinstance(workflow.fpath_container, Path)


def test_fpath_container_custom(workflow: PipelineWorkflow):
    fpath_custom = workflow.dpath_root / "my_container.sif"
    workflow.pipeline_config.CONTAINER_INFO.FILE = fpath_custom
    fpath_custom.touch()
    assert isinstance(workflow.fpath_container, Path)


def test_fpath_container_not_specified(workflow: PipelineWorkflow):
    workflow.pipeline_config.CONTAINER_INFO.FILE = None
    with pytest.raises(RuntimeError, match="No container image file specified"):
        workflow.fpath_container


def test_fpath_container_not_found(workflow: PipelineWorkflow):
    with pytest.raises(FileNotFoundError, match="No container image file found at"):
        workflow.fpath_container


@pytest.mark.parametrize(
    "pipeline_name,pipeline_version,pipeline_step,descriptor",
    [
        ("fmriprep", "23.1.3", None, {}),
        ("heudiconv", "0.12.2", "prepare", {"key1": "value1"}),
        ("my_pipeline", "1.0", None, {"key2": "value2"}),
    ],
)
def test_descriptor(
    workflow: PipelineWorkflow,
    pipeline_name,
    pipeline_version,
    pipeline_step,
    descriptor,
    tmp_path: Path,
):
    workflow.pipeline_name = pipeline_name
    workflow.pipeline_version = pipeline_version
    workflow.pipeline_step = pipeline_step

    # user-added pipelines with descriptor file
    fpath_descriptor = tmp_path / "custom_pipeline.json"
    workflow.pipeline_config.get_step_config().DESCRIPTOR_FILE = fpath_descriptor
    fpath_descriptor.write_text(json.dumps(descriptor))
    assert workflow.descriptor == descriptor


def test_descriptor_none(workflow: PipelineWorkflow):
    with pytest.raises(ValueError, match="No descriptor file specified for pipeline"):
        workflow.descriptor


@pytest.mark.parametrize(
    "substitutions,expected_descriptor",
    [
        ({"[[TO_REPLACE1]]": "value1"}, {"key1": "value1"}),
        ({"TO_REPLACE1": "value1"}, {"key1": "[[value1]]"}),
    ],
)
def test_descriptor_substitutions(
    tmp_path: Path, workflow: PipelineWorkflow, substitutions, expected_descriptor
):
    # set substitutions
    workflow.config.SUBSTITUTIONS = substitutions

    # set descriptor file and write descriptor content
    fpath_descriptor = tmp_path / "custom_pipeline.json"
    workflow.pipeline_config = ProcPipelineConfig(
        NAME=workflow.pipeline_name,
        VERSION=workflow.pipeline_version,
        STEPS=[ProcPipelineStepConfig(DESCRIPTOR_FILE=fpath_descriptor)],
    )

    fpath_descriptor.write_text(json.dumps({"key1": "[[TO_REPLACE1]]"}))

    assert workflow.descriptor == expected_descriptor


@pytest.mark.parametrize(
    "pipeline_name,pipeline_version,invocation",
    [
        ("my_pipeline", "1.0", {"key1": "val1", "key2": "val2"}),
        ("fmriprep", "23.1.3", {}),
    ],
)
def test_invocation(
    pipeline_name,
    pipeline_version,
    invocation,
    tmp_path: Path,
    workflow: PipelineWorkflow,
):
    workflow.pipeline_name = pipeline_name
    workflow.pipeline_version = pipeline_version

    fpath_invocation = tmp_path / "invocation.json"
    fpath_invocation.write_text(json.dumps(invocation))

    workflow.pipeline_config.get_step_config().INVOCATION_FILE = fpath_invocation
    assert workflow.invocation == invocation


def test_invocation_none(workflow: PipelineWorkflow):
    with pytest.raises(ValueError, match="No invocation file specified for pipeline"):
        workflow.invocation


@pytest.mark.parametrize(
    "substitutions,expected_invocation",
    [
        ({"[[TO_REPLACE1]]": "value1"}, {"key1": "value1"}),
        ({"TO_REPLACE1": "value1"}, {"key1": "[[value1]]"}),
    ],
)
def test_invocation_substitutions(
    tmp_path: Path, workflow: PipelineWorkflow, substitutions, expected_invocation
):
    # set substitutions
    workflow.config.SUBSTITUTIONS = substitutions

    # set invocation file and write invocation content
    fpath_invocation = tmp_path / "invocation.json"
    workflow.pipeline_config = ProcPipelineConfig(
        NAME=workflow.pipeline_name,
        VERSION=workflow.pipeline_version,
        STEPS=[ProcPipelineStepConfig(INVOCATION_FILE=fpath_invocation)],
    )
    fpath_invocation.write_text(json.dumps({"key1": "[[TO_REPLACE1]]"}))

    assert workflow.invocation == expected_invocation


@pytest.mark.parametrize(
    "pipeline_name,pipeline_version,patterns",
    [
        ("my_pipeline", "1.0", ["PATTERN1", "PATTERN2"]),
        ("fmriprep", "23.1.3", ["PATTERN3", "PATTERN4"]),
    ],
)
def test_pybids_ignore_patterns(
    pipeline_name,
    pipeline_version,
    patterns,
    tmp_path: Path,
    workflow: PipelineWorkflow,
):
    workflow.pipeline_name = pipeline_name
    workflow.pipeline_version = pipeline_version

    fpath_patterns = tmp_path / "pybids_ignore_patterns.json"
    fpath_patterns.write_text(json.dumps(patterns))
    workflow.pipeline_config.get_step_config().PYBIDS_IGNORE_FILE = fpath_patterns

    assert workflow.pybids_ignore_patterns == [
        re.compile(pattern) for pattern in patterns
    ]


def test_pybids_ignore_patterns_no_file(workflow: PipelineWorkflow):
    workflow.pipeline_config.get_step_config().PYBIDS_IGNORE_FILE = None
    assert workflow.pybids_ignore_patterns == []


def test_pybids_ignore_patterns_invalid_format(
    workflow: PipelineWorkflow, tmp_path: Path
):
    fpath_patterns = tmp_path / "pybids_ignore_patterns.json"
    fpath_patterns.write_text(json.dumps({"key": "value"}))
    workflow.pipeline_config.get_step_config().PYBIDS_IGNORE_FILE = fpath_patterns

    with pytest.raises(ValueError, match="Expected a list of strings"):
        workflow.pybids_ignore_patterns


@pytest.mark.parametrize("return_str", [True, False])
def test_process_template_json(return_str, tmp_path: Path):
    workflow = PipelineWorkflow(
        dpath_root=tmp_path / "my_dataset",
        pipeline_name="my_pipeline",
        pipeline_version="1.0",
    )

    class Test:
        extra2 = "extra_obj_attribute"

    processed = workflow.process_template_json(
        {
            "[[NIPOPPY_BIDS_PARTICIPANT]]": "[[NIPOPPY_PARTICIPANT_ID]]",
            "[[NIPOPPY_BIDS_SESSION]]": "[[NIPOPPY_SESSION_ID]]",
            "[[NIPOPPY_DPATH_PIPELINE]]": "[[NIPOPPY_DPATH_BIDS]]",
            "[[NIPOPPY_EXTRA1]]": "[[NIPOPPY_EXTRA2]]",
        },
        participant_id="01",
        session_id="1",
        extra1="extra_kwarg",
        objs=[Test()],
        return_str=return_str,
    )

    if return_str:
        assert isinstance(processed, str)
    else:
        assert isinstance(processed, dict)
        processed = json.dumps(processed)

    # check that everything was replaced
    for pattern in [
        "[[NIPOPPY_BIDS_PARTICIPANT]]",
        "[[NIPOPPY_PARTICIPANT_ID]]",
        "[[NIPOPPY_BIDS_SESSION]]",
        "[[NIPOPPY_SESSION_ID]]",
        "[[NIPOPPY_DPATH_PIPELINE]]",
        "[[NIPOPPY_DPATH_BIDS]]",
        "[[NIPOPPY_EXTRA1]]",
        "[[NIPOPPY_EXTRA2]]",
    ]:
        assert pattern not in processed


@pytest.mark.parametrize("participant_id,session_id", [("123", None), (None, "1")])
def test_process_template_json_error(participant_id, session_id, tmp_path: Path):
    workflow = PipelineWorkflow(
        dpath_root=tmp_path / "my_dataset",
        pipeline_name="my_pipeline",
        pipeline_version="1.0",
    )

    with pytest.raises(
        ValueError, match="participant_id and session_id must be strings"
    ):
        workflow.process_template_json(
            {},
            participant_id=participant_id,
            session_id=session_id,
        )


def test_boutiques_config(tmp_path: Path):
    workflow = PipelineWorkflow(
        dpath_root=tmp_path / "my_dataset",
        pipeline_name="my_pipeline",
        pipeline_version="1.0",
    )
    workflow.descriptor = {
        "custom": {
            "nipoppy": {"CONTAINER_CONFIG": {"ARGS": ["--pipeline-specific-arg"]}}
        }
    }

    boutiques_config = workflow.boutiques_config
    assert isinstance(boutiques_config, BoutiquesConfig)
    # should not be the default
    assert boutiques_config != BoutiquesConfig()


def test_boutiques_config_default(tmp_path: Path):
    workflow = PipelineWorkflow(
        dpath_root=tmp_path / "my_dataset",
        pipeline_name="no_boutiques_config",
        pipeline_version="1.0",
    )
    workflow.descriptor = {}
    boutiques_config = workflow.boutiques_config
    assert isinstance(boutiques_config, BoutiquesConfig)
    # expect the default
    assert boutiques_config == BoutiquesConfig()


def test_boutiques_config_invalid(tmp_path: Path):
    workflow = PipelineWorkflow(
        dpath_root=tmp_path / "my_dataset",
        pipeline_name="bad_boutiques_config",
        pipeline_version="1.0",
    )
    workflow.descriptor = {"custom": {"nipoppy": {"INVALID_ARG": "value"}}}

    with pytest.raises(ValueError, match="Error when loading the Boutiques config"):
        workflow.boutiques_config


@pytest.mark.parametrize(
    "participant_id,session_id,expected_count",
    [
        (None, None, 12),
        ("01", None, 6),
        ("02", None, 6),
        (None, "1", 5),
        (None, "2", 5),
        (None, "3", 2),
        ("01", "3", 2),
        ("02", "3", 0),
    ],
)
def test_set_up_bids_db(
    workflow: PipelineWorkflow,
    participant_id,
    session_id,
    expected_count,
    tmp_path: Path,
):
    dpath_bids_db = tmp_path / "bids_db"
    fids.create_fake_bids_dataset(
        output_dir=workflow.layout.dpath_bids,
        subjects="01",
        sessions=["1", "2", "3"],
        datatypes=["anat"],
    )
    fids.create_fake_bids_dataset(
        output_dir=workflow.layout.dpath_bids,
        subjects="02",
        sessions=["1", "2"],
        datatypes=["anat", "func"],
    )
    bids_layout = workflow.set_up_bids_db(
        dpath_bids_db=dpath_bids_db,
        participant_id=participant_id,
        session_id=session_id,
    )
    assert dpath_bids_db.exists()
    assert len(bids_layout.get(extension=".nii.gz")) == expected_count


def test_set_up_bids_db_ignore_patterns(workflow: PipelineWorkflow, tmp_path: Path):
    dpath_bids_db = tmp_path / "bids_db"
    participant_id = "01"
    session_id = "1"

    fids.create_fake_bids_dataset(
        output_dir=workflow.layout.dpath_bids,
    )

    pybids_ignore_patterns = workflow.pybids_ignore_patterns[:]

    workflow.set_up_bids_db(
        dpath_bids_db=dpath_bids_db,
        participant_id=participant_id,
        session_id=session_id,
    )

    assert pybids_ignore_patterns == workflow.pybids_ignore_patterns


@pytest.mark.parametrize(
    "pipeline_name,expected_version",
    [("heudiconv", "0.12.2"), ("fmriprep", "23.1.3"), ("my_pipeline", "1.0")],
)
def test_check_pipeline_version(
    pipeline_name,
    expected_version,
    workflow: PipelineWorkflow,
    caplog: pytest.LogCaptureFixture,
):
    # initialize with version=None
    workflow.pipeline_name = pipeline_name
    workflow.pipeline_version = None
    workflow.check_pipeline_version()
    assert workflow.pipeline_version == expected_version
    assert f"using version {expected_version}" in caplog.text


@pytest.mark.parametrize("dry_run", [True, False])
def test_run_setup_create_directories(dry_run: bool, tmp_path: Path):
    workflow = PipelineWorkflow(
        dpath_root=tmp_path / "my_dataset",
        pipeline_name="my_pipeline",
        pipeline_version="1.0",
        dry_run=dry_run,
    )
    create_empty_dataset(workflow.layout.dpath_root)
    workflow.run_setup()
    assert workflow.dpath_pipeline.exists() == (not dry_run)

    # run again, should not fail even if directories already exist
    workflow.run_setup()


@pytest.mark.parametrize(
    "participant_id,session_id,expected_count",
    [(None, None, 4), ("01", None, 3), ("01", "2", 1)],
)
def test_run_main(
    workflow: PipelineWorkflow,
    participant_id,
    session_id,
    expected_count,
):
    workflow.participant_id = participant_id
    workflow.session_id = session_id

    participants_and_sessions = {"01": ["1", "2", "3"], "02": ["1"]}
    manifest = prepare_dataset(
        participants_and_sessions_manifest=participants_and_sessions,
        participants_and_sessions_bidsified=participants_and_sessions,
        dpath_bidsified=workflow.layout.dpath_bids,
    )
    manifest.save_with_backup(workflow.layout.fpath_manifest)
    workflow.run_main()
    assert workflow._n_runs == expected_count


def test_run_main_catch_errors(workflow: PipelineWorkflow):
    workflow.participant_id = "FAIL"
    workflow.session_id = "1"

    participants_and_sessions = {workflow.participant_id: [workflow.session_id]}
    manifest = prepare_dataset(
        participants_and_sessions_manifest=participants_and_sessions,
        participants_and_sessions_bidsified=participants_and_sessions,
        dpath_bidsified=workflow.layout.dpath_bids,
    )
    manifest.save_with_backup(workflow.layout.fpath_manifest)
    workflow.run_main()
    assert workflow._n_runs == 1
    assert workflow._n_errors == 1


@pytest.mark.parametrize(
    "pipeline_name,pipeline_version,participant_id,session_id,expected_stem",
    [
        (
            "my_pipeline",
            "1.0",
            "sub1",
            None,
            "test/my_pipeline-1.0/my_pipeline-1.0-sub1",
        ),
        (
            "my_pipeline",
            None,
            "sub1",
            None,
            "test/my_pipeline-1.0/my_pipeline-1.0-sub1",
        ),
        ("fmriprep", None, None, "1", "test/fmriprep-23.1.3/fmriprep-23.1.3-1"),
    ],
)
def test_generate_fpath_log(
    pipeline_name,
    pipeline_version,
    participant_id,
    session_id,
    expected_stem,
    workflow: PipelineWorkflow,
    datetime_fixture,  # noqa F811
):
    workflow.pipeline_name = pipeline_name
    workflow.pipeline_version = pipeline_version
    workflow.participant_id = participant_id
    workflow.session_id = session_id
    fpath_log = workflow.generate_fpath_log()
    assert (
        fpath_log == workflow.layout.dpath_logs / f"{expected_stem}-20240404_1234.log"
    )
