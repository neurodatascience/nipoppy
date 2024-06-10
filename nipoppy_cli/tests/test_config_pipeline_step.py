"""Tests for the pipeline step configuration class."""

import pytest
from pydantic import ValidationError

from nipoppy.config.pipeline import PipelineStepConfig

FIELDS_STEP = [
    "NAME",
    "DESCRIPTOR_FILE",
    "INVOCATION_FILE",
    "PYBIDS_IGNORE_FILE",
    "CONTAINER_CONFIG",
]


@pytest.mark.parametrize(
    "data",
    [
        {"NAME": "step_name"},
        {"DESCRIPTOR_FILE": "PATH_TO_DESCRIPTOR_FILE"},
        {"INVOCATION_FILE": "PATH_TO_INVOCATION_FILE"},
        {"PYBIDS_IGNORE_FILE": "PATH_TO_PYBIDS_IGNORE_FILE"},
        {"CONTAINER_CONFIG": {}},
    ],
)
def test_field(data):
    pipeline_step_config = PipelineStepConfig(**data)
    for field in FIELDS_STEP:
        assert hasattr(pipeline_step_config, field)

    assert len(set(pipeline_step_config.model_fields.keys())) == len(FIELDS_STEP)


def test_no_extra_field():
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        PipelineStepConfig(not_a_field="a")
