"""Tests for the BaseWorkflow class."""

import logging
import subprocess
from pathlib import Path

import pytest

from nipoppy.workflows.base import BaseWorkflow, LogPrefix, _log_command, _run_command


@pytest.fixture()
def workflow():
    class DummyWorkflow(BaseWorkflow):
        def run_main(self):
            pass

    workflow = DummyWorkflow(name="my_workflow")

    return workflow


def test_abstract_class():
    with pytest.raises(TypeError, match="Can't instantiate abstract class"):
        BaseWorkflow(None, None)


def test_init(workflow: BaseWorkflow):
    assert workflow.name == "my_workflow"
    assert workflow.return_code == 0


@pytest.mark.parametrize("command", ["echo x", "echo y"])
@pytest.mark.no_xdist
def test_log_command(command, caplog: pytest.LogCaptureFixture):
    _log_command(command)
    assert caplog.records
    record = caplog.records[-1]
    assert record.levelno == logging.INFO
    assert record.message.startswith(LogPrefix.RUN)
    assert command in record.message


def test_run(workflow: BaseWorkflow):
    assert workflow.run() is None


# TODO we might want to move these tests to a separate test file or reorganize them
# Previously, were using the BaseWorkflow.run_command method, which has been extracted
# to a standalone function. The tests have been adapted accordingly.
@pytest.mark.no_xdist
def test_log_command_no_markup(caplog: pytest.LogCaptureFixture):
    # message with closing tag
    message = "[/]"

    # this should not raise a rich markup error
    _run_command(["echo", message])
    assert message in caplog.text


def test_run_command(tmp_path: Path):
    fpath = tmp_path / "test.txt"
    process = _run_command(["touch", fpath])
    assert process.returncode == 0
    assert fpath.exists()


@pytest.mark.no_xdist
def test_run_command_capture_output(tmp_path: Path):
    fpath = tmp_path / "test.txt"
    process, (stdout, stderr) = _run_command(["echo", fpath], capture_output=True)
    assert process.returncode == 0
    assert stdout == str(fpath)
    assert stderr == ""


def test_run_command_single_string(tmp_path: Path):
    fpath = tmp_path / "test.txt"
    process = _run_command(f"touch {fpath}", shell=True)
    assert process.returncode == 0
    assert fpath.exists()


def test_run_command_dry_run(tmp_path: Path):
    fpath = tmp_path / "test.txt"
    command = _run_command(["touch", fpath], dry_run=True)
    assert command == f"touch {fpath}"
    assert not fpath.exists()


def test_run_command_check():
    with pytest.raises(subprocess.CalledProcessError):
        _run_command(["which", "probably_fake_command"], check=True)


@pytest.mark.no_xdist
def test_run_command_no_markup(caplog: pytest.LogCaptureFixture, tmp_path: Path):
    # text with closing tag
    text = "[/]"

    # this should not raise a rich markup error
    fpath_txt = tmp_path / "test.txt"
    fpath_txt.write_text(text)
    _run_command(["cat", fpath_txt])
    assert text in caplog.text


@pytest.mark.no_xdist
def test_run_command_log_command_false(caplog: pytest.LogCaptureFixture):
    message = "This should be printed"
    _run_command(["echo", message], log_command=False)
    assert LogPrefix.RUN not in caplog.text
    assert LogPrefix.RUN_STDOUT in caplog.text
    assert message in caplog.text


@pytest.mark.no_xdist
def test_run_command_log_output_false(caplog: pytest.LogCaptureFixture):
    message = "This should be printed"
    _run_command(["echo", message], log_output=False)
    assert LogPrefix.RUN in caplog.text
    assert LogPrefix.RUN_STDOUT not in caplog.text
    assert message in caplog.text
