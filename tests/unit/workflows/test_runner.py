"""Tests for the Runner class."""

import copy
import json
from pathlib import Path

import pytest
import pytest_mock

from nipoppy.config.hpc import HpcConfig
from nipoppy.container import (
    ApptainerHandler,
    ContainerHandler,
    DockerHandler,
    SingularityHandler,
)
from nipoppy.env import ContainerCommandEnum
from nipoppy.exceptions import ConfigError
from nipoppy.pipeline_validation import check_pipeline_bundle
from nipoppy.utils.utils import get_pipeline_tag
from nipoppy.workflows.processing_runner import ProcessingRunner
from nipoppy.workflows.runner import Runner
from tests.conftest import (
    _set_up_substitution_testing,
    create_empty_dataset,
    create_pipeline_config_files,
    get_config,
    prepare_dataset,
)


@pytest.fixture(scope="function")
def runner(study, tmp_path: Path, mocker: pytest_mock.MockFixture) -> Runner:
    runner = ProcessingRunner(
        dpath_root=study.layout.dpath_root,
        pipeline_name="dummy_pipeline",
        pipeline_version="1.0.0",
    )
    runner.study = study

    create_empty_dataset(runner.study.layout.dpath_root)

    runner.study.config = get_config(
        container_config={
            "COMMAND": "apptainer",  # mocked
            "ARGS": ["--flag1"],
        },
    )

    mocker.patch(
        "nipoppy.container.shutil.which",
        side_effect=(lambda command: command),
    )

    fname_descriptor = "descriptor.json"
    fname_invocation = "invocation.json"

    fpath_container = tmp_path / "fake_container.sif"
    fpath_container.touch()

    create_pipeline_config_files(
        runner.study.layout.dpath_pipelines,
        processing_pipelines=[
            {
                "NAME": "dummy_pipeline",
                "VERSION": "1.0.0",
                "CONTAINER_CONFIG": {"ARGS": ["--flag2"]},
                "CONTAINER_INFO": {
                    "FILE": str(fpath_container),
                    "URI": "docker://dummy/image:1.0.0",
                },
                "STEPS": [
                    {
                        "DESCRIPTOR_FILE": fname_descriptor,
                        "INVOCATION_FILE": fname_invocation,
                        "CONTAINER_CONFIG": {"ARGS": ["--flag3"]},
                    },
                ],
            },
        ],
    )

    descriptor = {
        "name": "dummy_pipeline",
        "tool-version": "1.0.0",
        "description": "A dummy pipeline for testing",
        "schema-version": "0.5",
        "command-line": "echo [ARG1] [ARG2] [[NIPOPPY_DPATH_BIDS]]",
        "container-image": {
            "image": "dummy/image",
            "type": "docker",
        },
        "inputs": [
            {
                "id": "arg1",
                "name": "arg1",
                "type": "String",
                "command-line-flag": "--arg1",
                "value-key": "[ARG1]",
            },
            {
                "id": "arg2",
                "name": "arg2",
                "type": "Number",
                "command-line-flag": "--arg2",
                "value-key": "[ARG2]",
            },
        ],
        "custom": {"nipoppy": {"CONTAINER_SUBCOMMAND": "exec"}},
    }
    invocation = {
        "arg1": "[[NIPOPPY_PARTICIPANT_ID]] [[NIPOPPY_BIDS_SESSION_ID]]",
        "arg2": 10,
    }
    (runner.dpath_pipeline_bundle / fname_descriptor).write_text(json.dumps(descriptor))
    (runner.dpath_pipeline_bundle / fname_invocation).write_text(json.dumps(invocation))

    participants_and_sessions = {"01": ["1", "2", "3"], "02": ["1"]}
    create_empty_dataset(runner.study.layout.dpath_root)
    manifest = prepare_dataset(
        participants_and_sessions_manifest=participants_and_sessions,
        participants_and_sessions_bidsified=participants_and_sessions,
        dpath_bidsified=runner.study.layout.dpath_bids,
    )
    manifest.save_with_backup(runner.study.layout.fpath_manifest)
    return runner


def test_run_setup_validates_pipeline_bundle(
    runner: Runner, mocker: pytest_mock.MockFixture
):
    runner.pipeline_version = None
    mocked_check_pipeline_bundle = mocker.patch(
        "nipoppy.workflows.runner.check_pipeline_bundle",
        wraps=check_pipeline_bundle,
    )

    runner.run_setup()

    assert runner.pipeline_version == "1.0.0"
    mocked_check_pipeline_bundle.assert_called_once_with(
        runner.dpath_pipeline_bundle, strict=False
    )


def test_run_validation_error_prevents_execution(
    runner: Runner, mocker: pytest_mock.MockFixture
):
    error = ConfigError("Invalid pipeline bundle")
    mocker.patch(
        "nipoppy.workflows.runner.check_pipeline_bundle",
        side_effect=error,
    )
    mocked_run_main = mocker.patch.object(runner, "run_main")

    with pytest.raises(ConfigError, match="Invalid pipeline bundle"):
        runner.run()

    mocked_run_main.assert_not_called()


@pytest.mark.parametrize("hpc_config_data", [{}, {"CORES": "8", "MEMORY": "32G"}])
def test_hpc_config(
    hpc_config_data: dict,
    runner: Runner,
    tmp_path: Path,
    mocker: pytest_mock.MockFixture,
):
    fpath_hpc_config = tmp_path / "hpc_config.json"
    fpath_hpc_config.write_text(json.dumps(hpc_config_data))

    runner.pipeline_step_config.HPC_CONFIG_FILE = fpath_hpc_config.name
    runner.dpath_pipeline_bundle = fpath_hpc_config.parent

    mocked_process_template_json = _set_up_substitution_testing(runner, mocker)

    assert isinstance(runner.hpc_config, HpcConfig)

    # make sure substitutions are processed
    mocked_process_template_json.assert_called_once()


def test_hpc_config_no_file(runner: Runner):
    runner.pipeline_step_config.HPC_CONFIG_FILE = None
    assert runner.hpc_config == HpcConfig()


def test_hpc_runner(runner: Runner):
    assert runner.hpc_runner.subcommand == runner.subcommand


def test_submit_hpc_job(runner: Runner, mocker: pytest_mock.MockFixture):

    mocker.patch.object(
        runner,
        "_generate_cli_command_for_hpc",
        side_effect=(
            lambda participant_id, session_id: [
                "echo",
                f"{participant_id}, {session_id}",
            ]
        ),
    )

    n_jobs_submitted = 1
    mocked_submit = mocker.patch.object(
        runner.hpc_runner, "submit", return_value=n_jobs_submitted
    )

    participant_ids = ["participant1", "participant2"]
    session_ids = ["session1", "session2"]
    participants_sessions = list(zip(participant_ids, session_ids))
    runner._submit_hpc_job(participants_sessions)

    mocked_submit.assert_called_once_with(
        job_name=get_pipeline_tag(
            runner.pipeline_name,
            runner.pipeline_version,
            runner.pipeline_step,
            runner.participant_id,
            runner.session_id,
        ),
        job_array_commands=[
            "echo 'participant1, session1'",
            "echo 'participant2, session2'",
        ],
        participant_ids=participant_ids,
        session_ids=session_ids,
        dpath_work=runner.dpath_pipeline_work,
        dpath_hpc_logs=runner.study.layout.dpath_logs / runner.dname_hpc_logs,
        fname_hpc_error=runner.fname_hpc_error,
        fname_job_script=runner.fname_job_script,
        pipeline_name=runner.pipeline_name,
        pipeline_version=runner.pipeline_version,
        pipeline_step=runner.pipeline_step,
        dry_run=runner.dry_run,
    )

    assert runner.n_success == n_jobs_submitted
    assert runner.n_total == len(participants_sessions)


def test_run_main_hpc(mocker: pytest_mock.MockFixture, runner: Runner):
    mocker.patch("os.makedirs", mocker.MagicMock())
    mocked_submit_hpc_job = mocker.patch.object(runner, "_submit_hpc_job")

    runner.hpc = "exists"

    runner.run_main()

    mocked_submit_hpc_job.assert_called_once()

    assert list(mocked_submit_hpc_job.call_args[0][0]) == [
        ("01", "1"),
        ("01", "2"),
        ("01", "3"),
        ("02", "1"),
    ]


@pytest.mark.parametrize(
    "tar, extra_flags",
    [
        (True, ["--tar"]),
        (False, None),
    ],
)
def test_generate_cli_command_for_hpc(
    tar: bool,
    extra_flags: list[str] | None,
    runner: Runner,
    mocker: pytest_mock.MockFixture,
):
    mocked_generate_cli_command = mocker.patch.object(
        runner.hpc_runner,
        "generate_cli_command",
    )
    runner.tar = tar
    runner._generate_cli_command_for_hpc("p01", "s01")
    mocked_generate_cli_command.assert_called_once_with(
        participant_id="p01", session_id="s01", extra_flags=extra_flags
    )


@pytest.mark.parametrize(
    "uri,expected_image,expected_type",
    [
        ("docker://owner/project:1.0.0", "owner/project:1.0.0", "docker"),
        (
            "docker://ghcr.io/owner/project:1.0.0",
            "ghcr.io/owner/project:1.0.0",
            "docker",
        ),
        ("shub://owner/project:1.0.0", "owner/project:1.0.0", "singularity"),
        ("library://owner/project:1.0.0", "owner/project:1.0.0", "singularity"),
    ],
)
def test_inject_container_image(
    runner: Runner,
    uri: str,
    expected_image: str,
    expected_type: str,
):
    descriptor = runner._inject_container_image(descriptor=runner.descriptor, uri=uri)
    assert "container-image" in descriptor
    assert descriptor["container-image"]["image"] == expected_image
    assert descriptor["container-image"]["type"] == expected_type


def test_inject_container_image_invalid_uri(
    runner: Runner,
    caplog: pytest.LogCaptureFixture,
):
    runner._inject_container_image(descriptor=runner.descriptor, uri="invalid_uri")
    assert "Failed to parse CONTAINER_INFO.URI" in caplog.text


@pytest.mark.parametrize("simulate", [True, False])
def test_launch_boutiques_run(
    simulate, runner: Runner, mocker: pytest_mock.MockFixture
):
    runner.simulate = simulate

    participant_id = "01"
    session_id = "BL"

    mocked_run_command = mocker.patch("nipoppy.workflows.runner._run_command")

    descriptor_str, invocation_str = runner.launch_boutiques_run(
        participant_id, session_id
    )

    assert "[[NIPOPPY_DPATH_BIDS]]" not in descriptor_str
    assert "[[NIPOPPY_PARTICIPANT_ID]]" not in invocation_str
    assert "[[NIPOPPY_BIDS_SESSION_ID]]" not in invocation_str

    assert mocked_run_command.call_count == 1
    assert mocked_run_command.call_args[1].get("log_command") is False


@pytest.mark.parametrize(
    "container_handler,expected_container_opts",
    [
        (None, ["--no-container"]),
        (
            ApptainerHandler(),
            [
                "--force-apptainer",
                "--no-automounts",
                "--imagepath",
                "--container-opts=",
            ],
        ),
        (
            SingularityHandler(),
            [
                "--force-singularity",
                "--no-automounts",
                "--imagepath",
                "--container-opts=",
            ],
        ),
        (
            DockerHandler(),
            [
                "--force-docker",
                "--no-automounts",
                "--container-opts=",
            ],
        ),
    ],
)
@pytest.mark.parametrize("simulate", [True, False])
@pytest.mark.parametrize("verbose", [True, False])
@pytest.mark.no_xdist
def test_launch_boutiques_run_bosh_opts(
    container_handler,
    expected_container_opts,
    simulate,
    verbose,
    runner: Runner,
    mocker: pytest_mock.MockFixture,
    caplog: pytest.LogCaptureFixture,
):
    runner.simulate = simulate
    runner.verbose = verbose
    runner.descriptor["command-line"] = "echo [ARG1] [ARG2]"

    participant_id = "01"
    session_id = "BL"

    mocked_run_command = mocker.patch("nipoppy.workflows.runner._run_command")

    runner.launch_boutiques_run(
        participant_id,
        session_id,
        container_handler=container_handler,
    )

    if not simulate:
        # first positional argument
        bosh_command_args = mocked_run_command.call_args[0][0]

        for opt in expected_container_opts:
            assert opt in bosh_command_args, (
                f"Expected container option '{opt}' not found in {bosh_command_args}"
            )

        assert ("--debug" in bosh_command_args) == verbose

    else:
        assert "Additional launch options:" in caplog.text
        assert ("--debug" in caplog.text) == verbose


def test_launch_boutiques_run_bosh_no_container_image(
    runner: Runner,
    mocker: pytest_mock.MockFixture,
):
    runner.descriptor["command-line"] = "echo [ARG1] [ARG2]"
    runner.descriptor.pop("container-image")
    runner.pipeline_config.CONTAINER_INFO.URI = None

    participant_id = "01"
    session_id = "BL"

    mocked_run_command = mocker.patch("nipoppy.workflows.runner._run_command")

    runner.launch_boutiques_run(
        participant_id,
        session_id,
        container_handler=None,
    )

    container_opts = mocked_run_command.call_args[0][0]  # first positional argument
    assert "--no-container" in container_opts


def test_launch_boutiques_run_container_image(
    runner: Runner,
    mocker: pytest_mock.MockFixture,
):
    # remove [[NIPOPPY_DPATH_BIDS]]
    runner.descriptor["command-line"] = "echo [ARG1] [ARG2]"

    del runner.descriptor["container-image"]

    original_descriptor = copy.deepcopy(runner.descriptor)

    mocked_inject_container_image = mocker.patch.object(
        runner, "_inject_container_image", wraps=runner._inject_container_image
    )

    runner.launch_boutiques_run(participant_id="01", session_id="BL")

    mocked_inject_container_image.assert_called_with(
        original_descriptor,
        runner.pipeline_config.CONTAINER_INFO.URI,
    )


def test_launch_boutiques_run_no_container_image(
    runner: Runner,
    mocker: pytest_mock.MockFixture,
):
    # remove [[NIPOPPY_DPATH_BIDS]]
    runner.descriptor["command-line"] = "echo [ARG1] [ARG2]"

    mocked_inject_container_image = mocker.patch.object(
        runner, "_inject_container_image", wraps=runner._inject_container_image
    )

    runner.launch_boutiques_run(participant_id="01", session_id="BL")

    mocked_inject_container_image.assert_not_called()


def test_process_container_config(runner: Runner, tmp_path: Path):
    bind_path = tmp_path / "to_bind"
    container_command, container_handler = runner.process_container_config(
        participant_id="01", session_id="BL", bind_paths=[bind_path]
    )

    # check that the subcommand 'exec' from the Boutiques container config is used
    # note: the container command in the config is "echo" because otherwise the
    # check for the container command fails if Singularity/Apptainer is not on the PATH
    root_path = runner.study.layout.dpath_root.resolve()
    assert container_command.startswith("apptainer exec")
    assert f"--bind {root_path}:{root_path}:rw " in container_command
    assert container_command.endswith(
        f"--bind {bind_path.resolve()}:{bind_path.resolve()}:rw"
    )

    # check that the right container config was used
    assert "--flag1" in container_command
    assert "--flag2" in container_command
    assert "--flag3" in container_command

    # check that container config object matches command string
    assert isinstance(container_handler, ContainerHandler)
    assert container_handler.command == ContainerCommandEnum.APPTAINER.value
    assert "--bind" in container_handler.args
    assert f"{root_path}:{root_path}:rw" in container_handler.args
    assert f"{bind_path.resolve()}:{bind_path.resolve()}:rw" in container_handler.args
    assert "--flag1" in container_handler.args
    assert "--flag2" in container_handler.args
    assert "--flag3" in container_handler.args


def test_process_container_config_no_bind_cwd(
    runner: Runner, tmp_path: Path, mocker: pytest_mock.MockFixture
):
    bind_path = tmp_path / "to_bind"
    mocker.patch("pathlib.Path.cwd", return_value=bind_path)
    container_command, _ = runner.process_container_config(
        participant_id="01", session_id="BL", bind_paths=[bind_path]
    )

    assert (
        f"--bind {bind_path.resolve()}:{bind_path.resolve()}:rw"
        not in container_command
    )


def test_process_container_config_no_bindpaths(runner: Runner):
    # smoke test for no bind paths
    runner.process_container_config(participant_id="01", session_id="BL")
