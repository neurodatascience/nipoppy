"""Boutiques runner service."""

from __future__ import annotations

import subprocess
from typing import Protocol

from nipoppy.exceptions import ExecutionError
from nipoppy.logger import get_logger
from nipoppy.workflows.base import CommandRunner

logger = get_logger()


class BoshRunnerCallable(Protocol):
    """Protocol for the bosh runner callable."""

    def __call__(
        self,
        invocation_str: str,
        descriptor_str: str,
        bosh_exec_launch_args: list[str],
        run_command: CommandRunner | None,
        dry_run: bool,
    ) -> int:
        """Run the bosh command with the given arguments."""
        ...


class CommandBuilder(Protocol):
    """Protocol for a function that builds a command ro run.

    It takes the invocation, descriptor, and additional args and returns a list of
    command arguments.
    """

    def __call__(
        self,
        invocation: str,
        descriptor: str,
        args: list[str],
    ) -> list[str]:
        """Build command from invocation, descriptor, and extra args."""
        ...


class ErrorBuilder(Protocol):
    """Protocol for a function that builds an error message based on the exit code."""

    def __call__(self, exit_code: int) -> str:
        """Build error message based on the exit code."""
        ...


def _run_bosh_command(
    invocation_str: str,
    descriptor_str: str,
    run_command: CommandRunner,
    bosh_exec_launch_args: list[str] | None = None,
    dry_run: bool = False,
    *,
    mode: str,
    command_builder: CommandBuilder,
    error_message_builder: ErrorBuilder,
) -> int:
    """Execute a Boutiques command with shared error handling.

    Parameters
    ----------
    command_builder : CommandBuilder
        A function that builds the command to run based on the invocation, descriptor,
        and additional args. Returns a list of command arguments.
    error_message_builder : ErrorBuilder
        A function that builds an error message based on the exit code of a failed
        command.
    """
    if bosh_exec_launch_args is None:
        bosh_exec_launch_args = []

    command = command_builder(
        invocation_str,
        descriptor_str,
        bosh_exec_launch_args,
    )
    logger.info(f"{mode} pipeline command")

    try:
        run_command(command, log_command=False, dry_run=dry_run)
    except subprocess.CalledProcessError as exception:
        raise ExecutionError(error_message_builder(exception.returncode))

    return 0


def run_bosh_launch(
    invocation_str: str,
    descriptor_str: str,
    run_command: CommandRunner,
    bosh_exec_launch_args: list[str] | None = None,
    dry_run: bool = False,
) -> int:
    """Execute a Boutiques launch command.

    Parameters
    ----------
    invocation_str : str
        The Boutiques invocation as a JSON string.
    descriptor_str : str
        The Boutiques descriptor as a JSON string.
    run_command : CommandRunner, optional
        A function to execute the command. Should act like ``runner.run_command``.
    bosh_exec_launch_args : list of str, optional
        Additional arguments for ``bosh exec launch``.
    dry_run : bool, optional
        If True, build and log the command but skip actual execution.

    Returns
    -------
    int
        The return code.
    """

    def command_builder(invocation: str, descriptor: str, args: list[str]) -> list[str]:
        return [
            "bosh",
            "exec",
            "launch",
            "--stream",
            descriptor,
            invocation,
        ] + args

    def error_message_builder(exit_code: int) -> str:
        return (
            f"Pipeline execution failed (return code: {exit_code})."
            "Hint: make sure the shell command above is correct."
        )

    return _run_bosh_command(
        invocation_str=invocation_str,
        descriptor_str=descriptor_str,
        bosh_exec_launch_args=bosh_exec_launch_args,
        run_command=run_command,
        dry_run=dry_run,
        mode="Running",
        command_builder=command_builder,
        error_message_builder=error_message_builder,
    )


def run_bosh_simulate(
    invocation_str: str,
    descriptor_str: str,
    run_command: CommandRunner,
    bosh_exec_launch_args: list[str] | None = None,
    dry_run: bool = False,
) -> int:
    """Execute a Boutiques simulate command.

    Parameters
    ----------
    invocation_str : str
        The Boutiques invocation as a JSON string.
    descriptor_str : str
        The Boutiques descriptor as a JSON string.
    run_command : CommandRunner, optional
        A function to execute the command. Should act like ``runner.run_command``.
    bosh_exec_launch_args : list of str, optional
        Additional arguments for ``bosh exec launch``.
    dry_run : bool, optional
        If True, build and log the command but skip actual execution.

    Returns
    -------
    int
        The return code.
    """

    def command_builder(invocation: str, descriptor: str, args: list[str]) -> list[str]:
        return [
            "bosh",
            "exec",
            "simulate",
            "-i",
            invocation,
            descriptor,
        ]

    def error_message_builder(exit_code: int) -> str:
        return f"Pipeline simulation failed (return code: {exit_code})"

    logger.info(f"Additional launch options: {bosh_exec_launch_args}")
    rv = _run_bosh_command(
        invocation_str=invocation_str,
        descriptor_str=descriptor_str,
        bosh_exec_launch_args=bosh_exec_launch_args,
        run_command=run_command,
        dry_run=dry_run,
        mode="Simulating",
        command_builder=command_builder,
        error_message_builder=error_message_builder,
    )
    return rv
