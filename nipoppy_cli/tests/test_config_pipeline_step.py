"""Tests for the pipeline step configuration class."""

import pytest
from pydantic import BaseModel, ValidationError

from nipoppy.config.pipeline_step import (
    BasePipelineStepConfig,
    BidsPipelineStepConfig,
    ProcPipelineStepConfig,
)

FIELDS_STEP_BASE = [
    "NAME",
    "DESCRIPTOR_FILE",
    "INVOCATION_FILE",
    "CONTAINER_CONFIG",
]

FIELDS_STEP_PROC = FIELDS_STEP_BASE + ["PYBIDS_IGNORE_FILE"]
FIELDS_STEP_BIDS = FIELDS_STEP_BASE + ["UPDATE_DOUGHNUT"]


@pytest.mark.parametrize(
    "step_class,fields,data_list",
    [
        (
            BasePipelineStepConfig,
            FIELDS_STEP_BASE,
            [
                {"NAME": "step_name"},
                {"DESCRIPTOR_FILE": "PATH_TO_DESCRIPTOR_FILE"},
                {"INVOCATION_FILE": "PATH_TO_INVOCATION_FILE"},
                {"CONTAINER_CONFIG": {}},
            ],
        ),
        (
            BidsPipelineStepConfig,
            FIELDS_STEP_BIDS,
            [{"UPDATE_DOUGHNUT": True}],
        ),
        (
            ProcPipelineStepConfig,
            FIELDS_STEP_PROC,
            [{"PYBIDS_IGNORE_FILE": "PATH_TO_PYBIDS_IGNORE_FILE"}],
        ),
    ],
)
def test_field_base(step_class: type[BaseModel], fields, data_list):
    for data in data_list:
        pipeline_step_config = step_class(**data)
        for field in fields:
            assert hasattr(pipeline_step_config, field)

        assert len(set(pipeline_step_config.model_fields.keys())) == len(fields)


@pytest.mark.parametrize(
    "model_class",
    [ProcPipelineStepConfig, BidsPipelineStepConfig],
)
def test_no_extra_field(model_class):
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        model_class(not_a_field="a")
