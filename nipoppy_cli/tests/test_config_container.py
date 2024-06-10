"""Tests for container configuration and utilities."""

import os
from pathlib import Path

import pytest
from pydantic import ValidationError

from nipoppy.config.container import (
    ContainerConfig,
    ContainerInfo,
    SchemaWithContainerConfig,
    add_bind_path_to_args,
    check_container_args,
    check_container_command,
    prepare_container,
    set_container_env_vars,
)

FIELDS_CONTAINER_CONFIG = [
    "COMMAND",
    "ARGS",
    "ENV_VARS",
    "INHERIT",
]

FIELDS_CONTAINER_INFO = ["FILE", "URI"]


@pytest.mark.parametrize(
    "data",
    [
        {},
        {"COMMAND": "apptainer"},
        {"ARGS": ["--cleanenv", "-H /my/path"]},
        {"ENV_VARS": {"TEMPLATEFLOW_HOME": "/path/to/templateflow"}},
    ],
)
def test_container_config(data):
    container_config = ContainerConfig(**data)
    for field in FIELDS_CONTAINER_CONFIG:
        assert hasattr(container_config, field)
    assert len(container_config.model_fields) == len(FIELDS_CONTAINER_CONFIG)


@pytest.mark.parametrize(
    "data1,data2,data_expected",
    [
        (
            {"ARGS": ["--cleanenv"]},
            {"ARGS": ["--fakeroot"]},
            {"ARGS": ["--cleanenv", "--fakeroot"]},
        ),
        (
            {"ARGS": ["--cleanenv"]},
            {"ARGS": ["--cleanenv"]},
            {"ARGS": ["--cleanenv"]},
        ),
        (
            {"ARGS": ["--cleanenv"]},
            {"ARGS": ["--cleanenv", "--fakeroot"]},
            {"ARGS": ["--cleanenv", "--cleanenv", "--fakeroot"]},
        ),
        (
            {"ENV_VARS": {"VAR1": "1"}},
            {"ENV_VARS": {"VAR2": "2"}},
            {"ENV_VARS": {"VAR1": "1", "VAR2": "2"}},
        ),
        (
            {"ENV_VARS": {"VAR1": "1"}},
            {"ENV_VARS": {"VAR1": "111", "VAR2": "2"}},
            {"ENV_VARS": {"VAR1": "1", "VAR2": "2"}},
        ),
        (
            {"ENV_VARS": {"VAR1": "1"}},
            {"ENV_VARS": {"VAR1": "1"}},
            {"ENV_VARS": {"VAR1": "1"}},
        ),
    ],
)
def test_container_config_merge(data1, data2, data_expected):
    merged = ContainerConfig(**data1).merge(ContainerConfig(**data2))
    assert merged == ContainerConfig(**data_expected)


@pytest.mark.parametrize(
    "data1,data2,overwrite_command,data_expected",
    [
        (
            {"COMMAND": "apptainer"},
            {"COMMAND": "singularity"},
            True,
            {"COMMAND": "singularity"},
        ),
        (
            {"COMMAND": "apptainer"},
            {"COMMAND": "singularity"},
            False,
            {"COMMAND": "apptainer"},
        ),
    ],
)
def test_container_config_merge_overwrite_command(
    data1, data2, overwrite_command, data_expected
):
    merged = ContainerConfig(**data1).merge(
        ContainerConfig(**data2), overwrite_command=overwrite_command
    )
    assert merged == ContainerConfig(**data_expected)


def test_container_config_merge_error():
    with pytest.raises(TypeError, match="Cannot merge"):
        ContainerConfig().merge("bad_arg")


def test_container_config_no_extra_fields():
    with pytest.raises(ValidationError):
        ContainerConfig(not_a_field="a")


@pytest.mark.parametrize(
    "data",
    [
        {},
        {"FILE": "path/to/container.sif"},
        {"URI": "docker://my/container"},
    ],
)
def test_container_info(data):
    container_info = ContainerInfo(**data)
    for field in FIELDS_CONTAINER_INFO:
        assert hasattr(container_info, field)
    assert len(container_info.model_fields) == len(FIELDS_CONTAINER_INFO)


def test_container_info_no_extra_fields():
    with pytest.raises(ValidationError):
        ContainerInfo(not_a_field="a")


def test_schema_with_container_config():
    class ClassWithContainerConfig(SchemaWithContainerConfig):
        pass

    assert isinstance(
        ClassWithContainerConfig(a=1, b=2).get_container_config(),
        ContainerConfig,
    )


@pytest.mark.parametrize(
    "args,path_local,path_inside_container,mode,expected",
    [
        (
            [],
            "/my/local/path",
            "my/container/path",
            "ro",
            ["--bind", "/my/local/path:my/container/path:ro"],
        ),
        (
            ["other_arg"],
            "/my/local/path",
            None,
            "ro",
            ["other_arg", "--bind", "/my/local/path"],
        ),
        (
            [],
            "relative_path",
            None,
            "rw",
            [
                "--bind",
                f"{Path('relative_path').resolve()}",
            ],
        ),
    ],
)
def test_add_bind_path_to_args(args, path_local, path_inside_container, mode, expected):
    assert (
        add_bind_path_to_args(
            args,
            path_local=path_local,
            path_inside_container=path_inside_container,
            mode=mode,
        )
        == expected
    )


@pytest.mark.parametrize(
    "args",
    [
        [],
        ["--cleanenv"],
        ["--cleanenv", "--bind", "/"],
        ["--bind", "/", "--bind", "/:relative_path_in_container", "--bind", "/:/:ro"],
    ],
)
def test_check_container_args(args):
    # no change to arguments
    assert check_container_args(args=args) == args


def test_check_container_args_relative(caplog: pytest.LogCaptureFixture):
    assert check_container_args(args=["--bind", "."]) == [
        "--bind",
        str(Path(".").resolve()),
    ]
    assert "Resolving path" in caplog.text


def test_check_container_args_symlink(tmp_path: Path, caplog: pytest.LogCaptureFixture):
    path_symlink = tmp_path / "symlink"
    path_real = tmp_path / "file.txt"
    path_real.touch()
    path_symlink.symlink_to(path_real)
    assert check_container_args(args=["--bind", str(path_symlink)]) == [
        "--bind",
        str(path_real),
    ]
    assert "Resolving path" in caplog.text


def test_check_container_args_missing(tmp_path: Path, caplog: pytest.LogCaptureFixture):
    dpath = tmp_path / "missing"
    check_container_args(args=["--bind", str(dpath)])
    assert dpath.exists()
    assert "Creating missing directory" in caplog.text


def test_check_container_args_error():
    with pytest.raises(RuntimeError, match="Error parsing"):
        check_container_args(args=["--bind"])


@pytest.mark.parametrize("command", ["echo", "python"])
def test_check_container_command(command):
    # should not raise error
    check_container_command(command=command)


@pytest.mark.parametrize("command", ["123", "this_command_probably_does_not_exist123"])
def test_check_container_command_error(command):
    with pytest.raises(RuntimeError, match="Container executable not found"):
        check_container_command(command=command)


@pytest.mark.parametrize(
    "data, expected",
    [
        ({}, "apptainer run"),
        (
            {
                "COMMAND": "/path/to/singularity",
                "ARGS": ["--cleanenv"],
            },
            "/path/to/singularity run --cleanenv",
        ),
    ],
)
def test_prepare_container(data, expected):
    assert prepare_container(ContainerConfig(**data), check=False) == expected


@pytest.mark.parametrize(
    "env_vars",
    [
        {"VAR1": "1"},
        {"VAR2": "test"},
        {"VAR3": "123", "VAR4": ""},
    ],
)
def test_set_container_env_vars(env_vars: dict):
    set_container_env_vars(env_vars)
    for key, value in env_vars.items():
        assert os.environ[f"SINGULARITYENV_{key}"] == value
        assert os.environ[f"APPTAINERENV_{key}"] == value
