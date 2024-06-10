"""Tests for TrackerConfig class."""

import pytest

from nipoppy.config.tracker import TrackerConfig, check_tracker_configs

FIELDS_STEP = [
    "NAME",
    "PATHS",
]


@pytest.mark.parametrize(
    "data",
    [
        {"NAME": "pipeline_complete", "PATHS": ["path1", "path2"]},
    ],
)
def test_fields(data):
    tracker_config = TrackerConfig(**data)
    for field in FIELDS_STEP:
        assert hasattr(tracker_config, field)

    assert len(set(tracker_config.model_fields.keys())) == len(FIELDS_STEP)


def test_no_extra_field():
    with pytest.raises(ValueError, match="Extra inputs are not permitted"):
        TrackerConfig(not_a_field="a")


def test_at_least_one_path():
    with pytest.raises(ValueError, match="must contain at least one path"):
        TrackerConfig(NAME="pipeline_complete", PATHS=[])


def test_check_tracker_configs_duplicate_names():
    data = [
        TrackerConfig(NAME="a", PATHS=["a"]),
        TrackerConfig(NAME="a", PATHS=["b"]),
    ]
    with pytest.raises(ValueError, match="All tracker configs must have unique names"):
        check_tracker_configs(data)
