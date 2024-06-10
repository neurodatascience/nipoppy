"""Tests for the config module."""

import json
from contextlib import nullcontext
from pathlib import Path

import pytest
from pydantic import ValidationError

from nipoppy.config.container import ContainerConfig
from nipoppy.config.main import Config
from nipoppy.config.pipeline import PipelineConfig
from nipoppy.utils import FPATH_SAMPLE_CONFIG

from .conftest import DPATH_TEST_DATA

REQUIRED_FIELDS_CONFIG = ["DATASET_NAME", "VISITS", "PROC_PIPELINES"]
FIELDS_CONFIG = REQUIRED_FIELDS_CONFIG + [
    "SESSIONS",
    "SUBSTITUTIONS",
    "BIDS_PIPELINES",
    "CUSTOM",
    "CONTAINER_CONFIG",
    "DICOM_DIR_MAP_FILE",
    "DICOM_DIR_PARTICIPANT_FIRST",
]


@pytest.fixture(scope="function")
def valid_config_data():
    return {
        "DATASET_NAME": "my_dataset",
        "VISITS": ["1"],
        "SESSIONS": ["ses-1"],
        "BIDS_PIPELINES": [
            {
                "NAME": "bids_converter",
                "VERSION": "1.0",
                "CONTAINER_INFO": {"FILE": "path"},
                "STEPS": [{"NAME": "step1"}, {"NAME": "step2"}],
            },
            {
                "NAME": "bids_converter",
                "VERSION": "older_version",
            },
        ],
        "PROC_PIPELINES": [
            {"NAME": "pipeline1", "VERSION": "v1"},
            {
                "NAME": "pipeline1",
                "VERSION": "v2",
                "CONTAINER_INFO": {"FILE": "other_path"},
            },
            {"NAME": "pipeline2", "VERSION": "1.0", "CONTAINER_INFO": {"URI": "uri"}},
            {
                "NAME": "pipeline2",
                "VERSION": "2.0",
                "STEPS": [{"INVOCATION_FILE": "path"}],
            },
        ],
    }


def test_fields(valid_config_data: dict):
    config = Config(
        **{k: v for (k, v) in valid_config_data.items() if k in REQUIRED_FIELDS_CONFIG}
    )
    for field in FIELDS_CONFIG:
        assert hasattr(config, field)
    assert len(config.model_fields) == len(FIELDS_CONFIG)


def test_no_extra_fields(valid_config_data):
    with pytest.raises(ValidationError):
        Config(**valid_config_data, NOT_A_FIELD="x")


@pytest.mark.parametrize(
    "proc_pipelines_data,bids_pipelines_data",
    [
        (
            [
                {"NAME": "pipeline1", "VERSION": "v1"},
                {"NAME": "pipeline1", "VERSION": "v1"},
            ],
            [],
        ),
        (
            [],
            [
                {"NAME": "pipeline1", "VERSION": "v1", "STEPS": [{"NAME": "step1"}]},
                {"NAME": "pipeline1", "VERSION": "v1", "STEPS": [{"NAME": "step1"}]},
            ],
        ),
    ],
)
def test_check_no_duplicate_pipeline(
    valid_config_data, proc_pipelines_data, bids_pipelines_data
):
    valid_config_data["PROC_PIPELINES"] = proc_pipelines_data
    valid_config_data["BIDS_PIPELINES"] = bids_pipelines_data
    with pytest.raises(ValidationError, match="Found multiple configurations for"):
        Config(**valid_config_data)


@pytest.mark.parametrize(
    "visits,expected_sessions",
    [
        (["V01", "V02"], ["ses-V01", "ses-V02"]),
        (["ses-1", "2"], ["ses-1", "ses-2"]),
    ],
)
def test_sessions_inferred(visits, expected_sessions):
    data = {
        "DATASET_NAME": "my_dataset",
        "VISITS": visits,
        "BIDS_PIPELINES": [],
        "PROC_PIPELINES": [],
    }
    config = Config(**data)
    assert config.SESSIONS == expected_sessions


@pytest.mark.parametrize(
    "dicom_dir_map_file,dicom_dir_participant_first,is_valid",
    [
        (None, None, True),
        ("path", None, True),
        (None, True, True),
        (None, False, True),
        ("path", True, False),
    ],
)
def test_check_dicom_dir_options(
    valid_config_data, dicom_dir_map_file, dicom_dir_participant_first, is_valid
):
    valid_config_data["DICOM_DIR_MAP_FILE"] = dicom_dir_map_file
    valid_config_data["DICOM_DIR_PARTICIPANT_FIRST"] = dicom_dir_participant_first
    with (
        pytest.raises(ValueError, match="Cannot specify both")
        if not is_valid
        else nullcontext()
    ):
        assert isinstance(Config(**valid_config_data), Config)


@pytest.mark.parametrize(
    "data_root,data_pipeline,data_step,data_expected",
    [
        (
            {"ARGS": ["--cleanenv"]},
            {"ARGS": ["--fakeroot"]},
            {"ARGS": ["--no-home"]},
            {"ARGS": ["--no-home", "--fakeroot", "--cleanenv"]},
        ),
        (
            {"ARGS": ["--cleanenv"]},
            {"ARGS": ["--fakeroot"], "INHERIT": "false"},
            {},
            {"ARGS": ["--fakeroot"], "INHERIT": "true"},
        ),
        (
            {"ARGS": ["--cleanenv"]},
            {"ARGS": ["--fakeroot"]},
            {"ARGS": ["--no-home"], "INHERIT": "false"},
            {"ARGS": ["--no-home"], "INHERIT": "false"},
        ),
        (
            {"ARGS": ["--cleanenv"]},
            {},
            {"ARGS": ["--bind", "[[HEUDICONV_HEURISTIC_FILE]]"]},
            {"ARGS": ["--bind", "[[HEUDICONV_HEURISTIC_FILE]]", "--cleanenv"]},
        ),
        (
            {"ENV_VARS": {"VAR1": "1"}},
            {"ENV_VARS": {"VAR2": "2"}},
            {},
            {"ENV_VARS": {"VAR1": "1", "VAR2": "2"}},
        ),
        (
            {"ENV_VARS": {"VAR1": "1"}},
            {},
            {"ENV_VARS": {"VAR2": "2"}, "INHERIT": "false"},
            {"ENV_VARS": {"VAR2": "2"}, "INHERIT": "false"},
        ),
    ],
)
@pytest.mark.parametrize("pipeline_field", ["PROC_PIPELINES", "BIDS_PIPELINES"])
def test_propagate_container_config(
    valid_config_data,
    data_root,
    data_pipeline,
    data_step,
    data_expected,
    pipeline_field,
):
    pipeline_name = "pipeline1"
    pipeline_version = "1.0"
    step_name = "step1"
    data = valid_config_data
    container_config_key = "CONTAINER_CONFIG"
    data[container_config_key] = data_root
    data[pipeline_field] = [
        {
            "NAME": pipeline_name,
            "VERSION": pipeline_version,
            container_config_key: data_pipeline,
            "STEPS": [{"NAME": step_name, container_config_key: data_step}],
        }
    ]

    container_config = (
        Config(**data)
        .propagate_container_config()
        .get_pipeline_config(pipeline_name, pipeline_version)
        .get_step_config(step_name)
        .get_container_config()
    )

    assert container_config == ContainerConfig(**data_expected)


@pytest.mark.parametrize(
    "pipeline_name,expected_version",
    [("pipeline1", "v1"), ("pipeline2", "1.0"), ("bids_converter", "1.0")],
)
def test_get_pipeline_version(valid_config_data, pipeline_name, expected_version):
    config = Config(**valid_config_data)
    assert config.get_pipeline_version(pipeline_name) == expected_version


def test_get_pipeline_version_invalid_name(valid_config_data):
    with pytest.raises(ValueError, match="No config found for pipeline"):
        Config(**valid_config_data).get_pipeline_version("not_a_pipeline")


@pytest.mark.parametrize(
    "pipeline,version",
    [
        ("pipeline1", "v1"),
        ("pipeline2", "2.0"),
        ("bids_converter", "1.0"),
        ("bids_converter", "1.0"),
    ],
)
def test_get_pipeline_config(pipeline, version, valid_config_data):
    assert isinstance(
        Config(**valid_config_data).get_pipeline_config(pipeline, version),
        PipelineConfig,
    )


def test_get_pipeline_config_missing(valid_config_data):
    with pytest.raises(ValueError):
        Config(**valid_config_data).get_pipeline_config("not_a_pipeline", "v1")


def test_save(tmp_path: Path, valid_config_data):
    fpath_out = tmp_path / "config.json"
    config = Config(**valid_config_data)
    config.save(fpath_out)
    assert fpath_out.exists()
    with fpath_out.open("r") as file:
        assert isinstance(json.load(file), dict)


@pytest.mark.parametrize(
    "substitutions,json_obj,expected",
    [
        (
            {"VALUE1": "AAA", "VALUE2": "BBB"},
            {"KEY": "VALUE1 VALUE2"},
            {"KEY": "AAA BBB"},
        ),
        (
            {"VALUE1": "CCC", "VALUE2": "DDD"},
            ["AAA BBB VALUE1", "VALUE2"],
            ["AAA BBB CCC", "DDD"],
        ),
    ],
)
def test_apply_substitutions(valid_config_data, substitutions, json_obj, expected):
    config = Config(**valid_config_data, SUBSTITUTIONS=substitutions)
    assert config.apply_substitutions_to_json(json_obj) == expected


@pytest.mark.parametrize(
    "path",
    [
        FPATH_SAMPLE_CONFIG,
        DPATH_TEST_DATA / "config1.json",
        DPATH_TEST_DATA / "config2.json",
        DPATH_TEST_DATA / "config3.json",
    ],
)
def test_load(path):
    config = Config.load(path)
    assert isinstance(config, Config)
    for field in REQUIRED_FIELDS_CONFIG:
        assert hasattr(config, field)


@pytest.mark.parametrize(
    "path",
    [
        DPATH_TEST_DATA / "config_invalid1.json",  # missing required
        DPATH_TEST_DATA / "config_invalid2.json",  # invalid sessions
    ],
)
def test_load_invalid(path):
    with pytest.raises(ValueError):
        Config.load(path)


def test_load_apply_substitutions(valid_config_data, tmp_path: Path):
    pattern_to_replace1 = "[[FREESURFER_LICENSE_FILE]]"
    replacement_value1 = "/path/to/license.txt"
    pattern_to_replace2 = "[[TEMPLATEFLOW_HOME]]"
    replacement_value2 = "/path/to/templateflow"

    substitutions = {
        pattern_to_replace1: replacement_value1,
        pattern_to_replace2: replacement_value2,
    }
    valid_config_data["SUBSTITUTIONS"] = substitutions
    valid_config_data["PROC_PIPELINES"] = [
        {
            "NAME": "fmriprep",
            "VERSION": "23.1.3",
            "STEPS": [
                {
                    "INVOCATION_FILE": "path/to/invocation.json",
                    "CONTAINER_CONFIG": {
                        "ARGS": [
                            "--bind",
                            pattern_to_replace1,
                            "--bind",
                            pattern_to_replace2,
                        ],
                        "ENV_VARS": {"TEMPLATEFLOW_HOME": pattern_to_replace2},
                    },
                },
            ],
        },
    ]

    fpath = tmp_path / "config.json"
    Config(**valid_config_data).save(fpath)
    config_to_check = Config.load(fpath, apply_substitutions=True)
    assert config_to_check.PROC_PIPELINES[0] == PipelineConfig(
        **{
            "NAME": "fmriprep",
            "VERSION": "23.1.3",
            "STEPS": [
                {
                    "INVOCATION_FILE": "path/to/invocation.json",
                    "CONTAINER_CONFIG": {
                        "ARGS": [
                            "--bind",
                            replacement_value1,
                            "--bind",
                            replacement_value2,
                        ],
                        "ENV_VARS": {"TEMPLATEFLOW_HOME": replacement_value2},
                    },
                },
            ],
        },
    )

    # also check that the SUBSTITUTIONS field remains the same
    assert config_to_check.SUBSTITUTIONS == substitutions


@pytest.mark.parametrize(
    "apply_substitutions,substitutions",
    [
        (False, {"[[PATTERN1]]": "replacement1", "[[PATTERN2]]": "replacement2"}),
        (True, {}),
    ],
)
def test_load_no_substitutions(
    valid_config_data, tmp_path: Path, apply_substitutions, substitutions
):
    valid_config_data["SUBSTITUTIONS"] = substitutions
    valid_config_data["PROC_PIPELINES"] = [
        {
            "NAME": "fmriprep",
            "VERSION": "23.1.3",
            "STEPS": [
                {
                    "INVOCATION_FILE": "path/to/invocation.json",
                    "CONTAINER_CONFIG": {
                        "ARGS": [
                            "--bind",
                            "[[PATTERN1]]",
                            "--bind",
                            "[[PATERN2]]",
                        ],
                        "ENV_VARS": {"TEMPLATEFLOW_HOME": "[[PATTERN2]]"},
                    },
                },
            ],
        },
    ]

    fpath = tmp_path / "config.json"
    config_expected = Config(**valid_config_data)
    config_expected.save(fpath)

    # check that the loaded config is the same
    assert (
        Config.load(fpath, apply_substitutions=apply_substitutions) == config_expected
    )
