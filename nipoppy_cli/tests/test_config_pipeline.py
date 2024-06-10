"""Tests for the pipeline configuration class."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from nipoppy.config.pipeline import PipelineConfig, PipelineStepConfig

FIELDS_PIPELINE = [
    "NAME",
    "VERSION",
    "DESCRIPTION",
    "CONTAINER_INFO",
    "CONTAINER_CONFIG",
    "STEPS",
    "TRACKER_CONFIG_FILE",
]


@pytest.fixture(scope="function")
def valid_data() -> dict:
    return {
        "NAME": "my_pipeline",
        "VERSION": "1.0.0",
    }


@pytest.mark.parametrize(
    "additional_data",
    [
        {},
        {"DESCRIPTION": "My pipeline"},
        {"CONTAINER_CONFIG": {"ARGS": ["--cleanenv"]}},
        {"STEPS": []},
        {"TRACKER_CONFIG_FILE": "path/to/tracker/config/file"},
    ],
)
def test_fields(valid_data, additional_data):
    pipeline_config = PipelineConfig(**valid_data, **additional_data)
    for field in FIELDS_PIPELINE:
        assert hasattr(pipeline_config, field)

    assert len(set(pipeline_config.model_fields.keys())) == len(FIELDS_PIPELINE)


@pytest.mark.parametrize(
    "data",
    [{}, {"NAME": "my_pipeline"}, {"VERSION": "1.0.0"}],
)
def test_fields_missing_required(data):
    with pytest.raises(ValidationError):
        PipelineConfig(**data)


def test_fields_no_extra(valid_data):
    with pytest.raises(ValidationError):
        PipelineConfig(**valid_data, not_a_field="a")


def test_step_names_error_none(valid_data):
    with pytest.raises(
        ValidationError, match="Found at least one step with undefined NAME field"
    ):
        PipelineConfig(**valid_data, STEPS=[{}, {}])


def test_step_names_error_duplicate(valid_data):
    with pytest.raises(ValidationError, match="Found at least two steps with NAME"):
        PipelineConfig(
            **valid_data,
            STEPS=[
                {"NAME": "step1"},
                {"NAME": "step1"},
            ],
        )


@pytest.mark.parametrize("container", ["my_container.sif", "my_other_container.sif"])
def test_get_fpath_container(valid_data, container):
    pipeline_config = PipelineConfig(**valid_data, CONTAINER_INFO={"FILE": container})
    assert pipeline_config.get_fpath_container() == Path(container)


@pytest.mark.parametrize(
    "step_name,expected_name",
    [
        ("step1", "step1"),
        ("step2", "step2"),
        (None, "step1"),
    ],
)
def test_get_step_config(valid_data, step_name, expected_name):
    pipeling_config = PipelineConfig(
        **valid_data,
        STEPS=[
            PipelineStepConfig(NAME="step1", INVOCATION_FILE="step1.json"),
            PipelineStepConfig(NAME="step2", INVOCATION_FILE="step2.json"),
        ],
    )

    assert pipeling_config.get_step_config(step_name).NAME == expected_name


def test_get_step_config_no_steps(valid_data):
    pipeline_config = PipelineConfig(**valid_data, STEPS=[])
    with pytest.raises(ValueError, match="No steps specified for pipeline"):
        pipeline_config.get_step_config()


def test_get_step_config_invalid(valid_data):
    pipeline_config = PipelineConfig(
        **valid_data,
        STEPS=[
            PipelineStepConfig(NAME="step1", INVOCATION_FILE="step1.json"),
            PipelineStepConfig(NAME="step2", INVOCATION_FILE="step2.json"),
        ],
    )
    with pytest.raises(ValueError, match="not found in pipeline"):
        pipeline_config.get_step_config("invalid_step")


@pytest.mark.parametrize(
    "step_name,invocation_file",
    [("step1", Path("step1.json")), ("step2", Path("step2.json"))],
)
def test_get_invocation_file(valid_data, step_name, invocation_file):
    pipeline_config = PipelineConfig(
        **valid_data,
        STEPS=[
            PipelineStepConfig(NAME="step1", INVOCATION_FILE="step1.json"),
            PipelineStepConfig(NAME="step2", INVOCATION_FILE="step2.json"),
        ],
    )

    assert pipeline_config.get_invocation_file(step_name) == invocation_file


@pytest.mark.parametrize(
    "step_name,descriptor_file",
    [("step1", Path("step1.json")), ("step2", Path("step2.json"))],
)
def test_get_descriptor_file(valid_data, step_name, descriptor_file):
    pipeline_config = PipelineConfig(
        **valid_data,
        STEPS=[
            PipelineStepConfig(NAME="step1", DESCRIPTOR_FILE="step1.json"),
            PipelineStepConfig(NAME="step2", DESCRIPTOR_FILE="step2.json"),
        ],
    )

    assert pipeline_config.get_descriptor_file(step_name) == descriptor_file


@pytest.mark.parametrize(
    "step_name,pybids_ignore_file",
    [("step1", Path("patterns1.json")), ("step2", Path("patterns2.json"))],
)
def test_get_pybids_ignore(valid_data, step_name, pybids_ignore_file):
    pipeline_config = PipelineConfig(
        **valid_data,
        STEPS=[
            PipelineStepConfig(NAME="step1", PYBIDS_IGNORE_FILE="patterns1.json"),
            PipelineStepConfig(NAME="step2", PYBIDS_IGNORE_FILE="patterns2.json"),
        ],
    )

    assert pipeline_config.get_pybids_ignore_file(step_name) == pybids_ignore_file
