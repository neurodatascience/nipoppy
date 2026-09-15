"""Tests for container option handlers."""

import logging
from pathlib import Path
from typing import Type

import pytest
import pytest_mock

from nipoppy.config.container import ContainerConfig
from nipoppy.container import (
    ApptainerHandler,
    BareMetalHandler,
    ContainerHandler,
    DockerHandler,
    SingularityHandler,
    get_container_handler,
)
from nipoppy.exceptions import ContainerError


class _TestHandler(ContainerHandler):
    """Class name starts with underscore to avoid Pytest collection."""

    command = "test"
    bind_flags = ("-B", "--bind")

    def is_image_downloaded(self, uri, fpath_container):
        return True

    def get_pull_confirmation_prompt(self):
        return "not_used"

    def get_pull_command(self, uri, fpath_container):
        return "not_used"


@pytest.fixture
def handler() -> ContainerHandler:
    return _TestHandler()


@pytest.mark.parametrize(
    "subclass",
    [ApptainerHandler, SingularityHandler, DockerHandler],
)
def test_subclass(subclass: Type[ContainerHandler]):
    # try to instantiate subclass
    handler = subclass()
    assert isinstance(handler, ContainerHandler)
    assert len(handler.bind_flags) == 2


@pytest.mark.parametrize(
    "args,expected_args", [(None, []), (["--some-arg"], ["--some-arg"])]
)
def test_init_args(args, expected_args):
    handler = _TestHandler(args=args)
    assert handler.args == expected_args
    assert handler.args is not args


def test_check_command_exists(
    handler: ContainerHandler, mocker: pytest_mock.MockerFixture
):
    # should not raise error
    mocked_which = mocker.patch(
        "nipoppy.container.shutil.which", return_value="/some/path/to/command"
    )
    handler.check_command_exists()
    mocked_which.assert_called_once_with(handler.command)


def test_check_command_exists_error(
    handler: ContainerHandler, mocker: pytest_mock.MockerFixture
):
    mocker.patch("nipoppy.container.shutil.which", return_value=None)
    with pytest.raises(ContainerError, match="Container executable not found"):
        handler.check_command_exists()


@pytest.mark.parametrize(
    "args,path_local,path_inside_container,mode,expected",
    [
        (
            [],
            "/my/local/path",
            "my/container/path",
            "ro",
            ["-B", "/my/local/path:my/container/path:ro"],
        ),
        (
            ["other_arg"],
            "/my/local/path",
            None,
            "ro",
            ["other_arg", "-B", "/my/local/path:/my/local/path:ro"],
        ),
        (
            [],
            "relative_path",
            None,
            "rw",
            [
                "-B",
                f"{Path('relative_path').resolve()}:{Path('relative_path').resolve()}:rw",  # noqa: E501
            ],
        ),
        (
            [],
            "/my/local/path",
            None,
            None,
            ["-B", "/my/local/path:/my/local/path"],
        ),
    ],
)
def test_add_bind_arg(
    handler: ContainerHandler,
    args,
    path_local,
    path_inside_container,
    mode,
    expected,
):
    handler.args = args

    handler.add_bind_arg(
        path_src=path_local,
        path_dest=path_inside_container,
        mode=mode,
    )
    assert handler.args == expected


@pytest.mark.parametrize(
    "args",
    [
        [],
        ["--cleanenv"],
        ["--cleanenv", "-B", "/"],
        ["-B", "/", "-B", "/:relative_path_in_container", "-B", "/:/:ro"],
    ],
)
def test_fix_bind_args(args, handler: ContainerHandler):
    handler.args = args
    handler.fix_bind_args()

    # no change to arguments
    assert handler.args == args


@pytest.mark.no_xdist
@pytest.mark.parametrize("bind_flag", ["-B", "--bind"])
def test_fix_bind_args_relative(
    bind_flag, handler: ContainerHandler, caplog: pytest.LogCaptureFixture
):
    handler.args = [bind_flag, "."]
    caplog.set_level(logging.DEBUG)

    handler.fix_bind_args()

    assert handler.args == [bind_flag, str(Path(".").resolve())]
    assert "Resolving path" in caplog.text


@pytest.mark.no_xdist
def test_fix_bind_args_symlink(
    handler: ContainerHandler, tmp_path: Path, caplog: pytest.LogCaptureFixture
):
    path_symlink = tmp_path / "symlink"
    path_real = tmp_path / "file.txt"
    path_real.touch()
    path_symlink.symlink_to(path_real)

    handler.args = ["-B", str(path_symlink)]
    caplog.set_level(logging.DEBUG)

    handler.fix_bind_args()

    assert handler.args == ["-B", str(path_real)]
    assert "Resolving path" in caplog.text


@pytest.mark.no_xdist
def test_fix_bind_args_missing(
    handler: ContainerHandler, tmp_path: Path, caplog: pytest.LogCaptureFixture
):
    dpath = tmp_path / "missing"
    assert not dpath.exists()

    handler.args = ["-B", str(dpath)]
    caplog.set_level(logging.DEBUG)

    handler.fix_bind_args()

    assert dpath.exists()
    assert "Creating missing directory" in caplog.text


def test_fix_bind_args_error(handler: ContainerHandler):
    handler.args = ["-B"]
    with pytest.raises(ContainerError, match="Error parsing"):
        handler.fix_bind_args()


def test_add_env_arg(handler: ContainerHandler):
    handler.add_env_arg("VAR1", "1")
    assert handler.args == ["--env", "VAR1=1"]


@pytest.mark.parametrize(
    "handler,subcommand,expected",
    [
        (
            ApptainerHandler(args=["--env", "VAR1=1"]),
            "run",
            "apptainer run --env VAR1=1",
        ),
        (
            SingularityHandler(args=["--cleanenv"]),
            "exec",
            "singularity exec --cleanenv",
        ),
        (
            DockerHandler(
                args=["--volume", ".:/container/path:ro", "--env", "VAR2=value"]
            ),
            "run",
            f"docker run --volume {Path('.').resolve()}:/container/path:ro --env VAR2=value",  # noqa: E501
        ),
    ],
)
def test_get_shell_command(
    handler: ContainerHandler,
    subcommand: str,
    expected: str,
    mocker: pytest_mock.MockerFixture,
):
    # pretend command exists
    mocked_check_command_exists = mocker.patch.object(handler, "check_command_exists")
    assert handler.get_shell_command(subcommand=subcommand) == expected
    mocked_check_command_exists.assert_called_once()


@pytest.mark.parametrize(
    "uri,fname_container,exists",
    [
        ("docker://test/test:latest", "exists.sif", True),
        ("docker://test/test:latest", "does_not_exist.sif", False),
    ],
)
@pytest.mark.parametrize("handler", [ApptainerHandler(), SingularityHandler()])
def test_is_image_downloaded_apptainer_singularity(
    handler: ContainerHandler,
    uri,
    fname_container,
    exists,
    tmp_path: Path,
):
    (tmp_path / "exists.sif").touch()

    assert handler.is_image_downloaded(uri, tmp_path / fname_container) == exists


@pytest.mark.parametrize("handler", [ApptainerHandler(), SingularityHandler()])
def test_is_image_downloaded_apptainer_singularity_error(
    handler: ContainerHandler,
):
    with pytest.raises(
        ContainerError, match="Path to container image must be specified"
    ):
        handler.is_image_downloaded("ignored", None)


@pytest.mark.parametrize(
    "uri,exists",
    [
        ("docker://test/downloaded_image:latest", True),
        ("test/downloaded_image:latest", True),
        ("docker://test/missing_image:latest", False),
        ("missing_image:latest", False),
    ],
)
def test_is_image_downloaded_docker(
    uri,
    exists,
    mocker: pytest_mock.MockerFixture,
):
    handler = DockerHandler()

    # mock subprocess.run to simulate docker image existing
    def mock_run(cmd, *args, **kwargs):
        class MockCompletedProcess:
            def __init__(self, returncode, stdout):
                self.returncode = returncode
                self.stdout = stdout

        if cmd == ["docker", "image", "inspect", "test/downloaded_image:latest"]:
            return MockCompletedProcess(0, "test/downloaded_image:latest\n")
        else:
            return MockCompletedProcess(1, "")

    mocker.patch("nipoppy.container.subprocess.run", side_effect=mock_run)

    assert handler.is_image_downloaded(uri, "not_used") == exists


def test_is_image_downloaded_docker_error():
    handler = DockerHandler()

    with pytest.raises(ContainerError, match="URI must be specified"):
        assert handler.is_image_downloaded(None, "not_used")


def test_is_image_downloaded_baremetal():
    handler = BareMetalHandler()

    assert handler.is_image_downloaded("not_used", "not_used") is True


@pytest.mark.parametrize(
    "handler,uri,expected_command,machine",
    [
        (
            ApptainerHandler(),
            "docker://test/test:latest",
            "apptainer pull path/to/container.sif docker://test/test:latest",
            "not_used",
        ),
        (
            SingularityHandler(),
            "docker://test/test:latest",
            "singularity pull path/to/container.sif docker://test/test:latest",
            "not_used",
        ),
        (
            DockerHandler(),
            "docker://test/test:latest",
            "docker pull test/test:latest",
            "x86_64",
        ),
        (
            DockerHandler(),
            "test/test:latest",
            "docker pull --platform=linux/amd64 test/test:latest",
            "amd64",
        ),
    ],
)
def test_get_pull_command(
    handler: ContainerHandler,
    uri,
    expected_command,
    mocker: pytest_mock.MockerFixture,
    machine,
):
    mocker.patch("platform.machine", return_value=machine)
    fpath_container = "path/to/container.sif"
    assert handler.get_pull_command(uri, fpath_container) == expected_command


@pytest.mark.parametrize(
    "handler,uri,fpath_container,error_message",
    [
        (
            ApptainerHandler(),
            "docker://test/test:latest",
            None,
            "Both URI and path to container image must be specified",
        ),
        (
            ApptainerHandler(),
            None,
            "path/to/container.sif",
            "Both URI and path to container image must be specified",
        ),
        (
            SingularityHandler(),
            "docker://test/test:latest",
            None,
            "Both URI and path to container image must be specified",
        ),
        (
            SingularityHandler(),
            None,
            "path/to/container.sif",
            "Both URI and path to container image must be specified",
        ),
        (
            DockerHandler(),
            None,
            "ignored",
            "URI must be specified",
        ),
    ],
)
def test_get_pull_command_error(
    handler: ContainerHandler, uri, fpath_container, error_message
):
    with pytest.raises(ContainerError, match=error_message):
        handler.get_pull_command(uri, fpath_container)


@pytest.mark.parametrize(
    "config,expected",
    [
        (
            ContainerConfig(
                COMMAND="apptainer",
                ARGS=["--cleanenv", "--bind", "fake_path"],
                BIND_PATHS=["/other_path"],
                ENV_VARS={"VAR1": "1"},
            ),
            ApptainerHandler(
                args=[
                    "--cleanenv",
                    "--bind",
                    "fake_path",
                    "--bind",
                    "/other_path:/other_path:rw",
                    "--env",
                    "VAR1=1",
                ],
            ),
        ),
        (
            ContainerConfig(
                COMMAND="singularity",
                ARGS=[],
            ),
            SingularityHandler(
                args=[],
            ),
        ),
        (
            ContainerConfig(
                COMMAND="docker",
                ARGS=["--volume", "path"],
                BIND_PATHS=["/path2:/inside_container:ro"],
                ENV_VARS={"VAR3": "123"},
            ),
            DockerHandler(
                args=[
                    "--volume",
                    "path",
                    "--volume",
                    "/path2:/inside_container:ro",
                    "--env",
                    "VAR3=123",
                ],
            ),
        ),
        (
            ContainerConfig(
                COMMAND=None,
                ARGS=[],
                BIND_PATHS=["ignored"],
                ENV_VARS={"VAR3": "123"},
            ),
            BareMetalHandler(),
        ),
    ],
)
def test_get_container_handler(config: ContainerConfig, expected: ContainerHandler):
    handler = get_container_handler(config)
    assert isinstance(handler, expected.__class__)
    assert handler.env_flag == expected.env_flag
    assert handler.command == expected.command
    assert handler.bind_flags == expected.bind_flags
    assert handler.args == expected.args


def test_get_container_handler_error():
    config = ContainerConfig()
    config.COMMAND = "unknown_command"
    with pytest.raises(ContainerError, match="No container handler for command:"):
        get_container_handler(config)


@pytest.mark.parametrize(
    "handler, expected",
    [
        (
            ApptainerHandler(),
            "This pipeline is containerized: do you want to download the container "
            "(to [magenta]{fpath_container}[/])?",
        ),
        (
            SingularityHandler(),
            "This pipeline is containerized: do you want to download the container "
            "(to [magenta]{fpath_container}[/])?",
        ),
        (
            DockerHandler(),
            "This pipeline is containerized: do you want to download the container "
            "locally?",
        ),
    ],
)
def test_confirmation_prompt(handler: ContainerHandler, expected: str):
    FPATH_CONTAINER = "test_container.sif"
    prompt = handler.get_pull_confirmation_prompt(FPATH_CONTAINER)
    # This is ignored when there is nothing to format
    assert prompt == expected.format(fpath_container=FPATH_CONTAINER)
