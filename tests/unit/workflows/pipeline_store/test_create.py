"""Tests for PipelineCreateWorkflow class."""

from pathlib import Path

import pytest

from nipoppy.env import PROGRAM_VERSION, PipelineTypeEnum
from nipoppy.exceptions import FileOperationError, WorkflowError
from nipoppy.pipeline_validation import check_pipeline_bundle
from nipoppy.utils.utils import TEMPLATE_PIPELINE_PATH, load_json
from nipoppy.workflows.pipeline_store.create import (
    PipelineCreateWorkflow,
)
from tests.conftest import TEST_PIPELINE


def _has_same_JSON_content(a: Path, b: Path) -> bool:
    """Check if two files have the same JSON content."""
    return load_json(a, allow_json5=True) == load_json(b, allow_json5=True)


def _has_correct_JSON5_comment(path: Path) -> bool:
    """Check that the comment is preserved and that the substitution was applied."""
    content = path.read_text()
    return (
        (
            "// Nipoppy will apply string substitutions when this file is loaded"
            in content
        )
        and ("[[NIPOPPY_VERSION]]" not in content)
        and (PROGRAM_VERSION in content)
    )


@pytest.fixture(scope="function")
def target(tmp_path: Path) -> Path:
    """Fixture to provide a target directory for the tests."""
    return tmp_path / "target"


@pytest.fixture(scope="function")
def workflow(target: Path) -> PipelineCreateWorkflow:
    """Fixture to provide a PipelineCreateWorkflow instance for the tests."""
    return PipelineCreateWorkflow(
        pipeline_dir=target,
        type_=PipelineTypeEnum.PROCESSING,
    )


@pytest.mark.parametrize(
    "type_",
    [
        PipelineTypeEnum.BIDSIFICATION,
        PipelineTypeEnum.PROCESSING,
        PipelineTypeEnum.EXTRACTION,
    ],
)
def test_create(
    workflow: PipelineCreateWorkflow,
    type_: PipelineTypeEnum,
    recwarn: pytest.WarningsRecorder,
):
    """Test the creation of a pipeline bundle."""
    assert not workflow.pipeline_dir.exists()

    # Run the workflow
    workflow.type_ = type_
    workflow.run_main()

    check_pipeline_bundle(workflow.pipeline_dir)

    # Check the bundle content exists and is correct
    descriptor_file_path = workflow.pipeline_dir.joinpath("descriptor.json")
    assert descriptor_file_path.is_file()
    assert _has_same_JSON_content(
        descriptor_file_path,
        TEMPLATE_PIPELINE_PATH.joinpath("descriptor.json"),
    )

    invocation_file_path = workflow.pipeline_dir.joinpath("invocation.json5")
    assert invocation_file_path.is_file()
    # Cannot compare the content of the invocation.json file
    # because boutiques generates random arg values.
    # Instead, we compare the keys of the JSON object
    assert set(load_json(invocation_file_path, allow_json5=True).keys()) == {
        "basic_param2"
    }
    assert _has_correct_JSON5_comment(invocation_file_path)

    hpc_file_path = workflow.pipeline_dir.joinpath("hpc.json5")
    assert hpc_file_path.is_file()
    assert _has_same_JSON_content(
        hpc_file_path,
        TEMPLATE_PIPELINE_PATH.joinpath("hpc.json5"),
    )
    assert _has_correct_JSON5_comment(hpc_file_path)

    pipeline_config_file_path = workflow.pipeline_dir.joinpath("config.json")
    assert pipeline_config_file_path.is_file()
    assert _has_same_JSON_content(
        pipeline_config_file_path,
        TEMPLATE_PIPELINE_PATH.joinpath(f"config-{type_.value}.json5"),
    )
    assert _has_correct_JSON5_comment(pipeline_config_file_path)

    if type_ == PipelineTypeEnum.PROCESSING:
        tracker_file_path = workflow.pipeline_dir.joinpath("tracker.json5")
        assert tracker_file_path.is_file()
        assert _has_same_JSON_content(
            tracker_file_path,
            TEMPLATE_PIPELINE_PATH.joinpath("tracker.json5"),
        )
        assert _has_correct_JSON5_comment(tracker_file_path)

    assert not any("Unable to replace" in str(warning.message) for warning in recwarn)


def test_create_already_exists(workflow: PipelineCreateWorkflow):
    """Test the behavior when the target directory already exists."""
    workflow.pipeline_dir.mkdir(parents=True, exist_ok=True)
    assert workflow.pipeline_dir.exists()

    with pytest.raises(FileOperationError, match="Target directory .* already exists"):
        workflow.run_main()


def test_create_from_descriptor(workflow: PipelineCreateWorkflow):
    """Test the behavior when the bundle is created from a descriptor."""
    source_descriptor = TEST_PIPELINE / "descriptor.json"

    workflow.source_descriptor = source_descriptor
    workflow.run_main()

    check_pipeline_bundle(workflow.pipeline_dir)

    assert _has_same_JSON_content(
        workflow.pipeline_dir.joinpath("descriptor.json"), source_descriptor
    )

    assert set(
        load_json(
            workflow.pipeline_dir.joinpath("invocation.json5"), allow_json5=True
        ).keys()
    ) == {
        "bids_dir",
        "output_dir",
        "analysis_level",
    }

    descriptor = load_json(workflow.pipeline_dir.joinpath("descriptor.json"))
    config = load_json(workflow.pipeline_dir.joinpath("config.json"), allow_json5=True)
    assert config["NAME"] == descriptor["name"]
    assert config["VERSION"] == descriptor["tool-version"]
    assert (
        config["CONTAINER_INFO"]["URI"]
        == "docker://nipreps/[[PIPELINE_NAME]]:[[PIPELINE_VERSION]]"
    )


@pytest.mark.parametrize("file_content", ["", "{}"])
def test_create_invalid_descriptor(
    tmp_path: Path,
    workflow: PipelineCreateWorkflow,
    file_content: str,
):
    """Test the behavior when the source descriptor is invalid."""
    source_descriptor = tmp_path / "bad_descriptor.json"
    source_descriptor.write_text(file_content)

    workflow.source_descriptor = source_descriptor

    with pytest.raises(WorkflowError, match="Error validating the descriptor file .*:"):
        workflow.run_main()
