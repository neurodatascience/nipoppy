"""Workflow utilities."""

from __future__ import annotations

import logging
import shlex
import subprocess
from abc import ABC, abstractmethod
from collections.abc import Sequence
from functools import cached_property
from pathlib import Path
from typing import Protocol

from nipoppy.base import Base
from nipoppy.env import EXT_LOG, PROGRAM_NAME, StrOrPathLike
from nipoppy.exceptions import FileOperationError, ReturnCode
from nipoppy.layout import DatasetLayout
from nipoppy.logger import get_logger
from nipoppy.study import Study
from nipoppy.tabular.curation_status import (
    CurationStatusTable,
    generate_curation_status_table,
)
from nipoppy.tabular.dicom_dir_map import DicomDirMap
from nipoppy.tabular.processing_status import ProcessingStatusTable
from nipoppy.utils.utils import (
    add_path_timestamp,
    is_nipoppy_project,
)

logger = get_logger()


class LogPrefix:
    """Prefixes for logging subprocess output."""

    RUN = "[RUN]"
    RUN_STDOUT = "[RUN STDOUT]"
    RUN_STDERR = "[RUN STDERR]"


def _log_command(command: str):
    """Write a command to the log with a special prefix."""
    # using extra={"markup": False} in case the command contains substrings
    # that would be interpreted as closing tags by the RichHandler
    logger.info(f"{LogPrefix.RUN} {command}", extra={"markup": False})


class CommandRunner(Protocol):
    """Protocol for functions that run commands, used for strategy injection."""

    def __call__(
        self,
        command_or_args: Sequence[str] | str,
        /,
        *,
        check: bool = True,
        log_command: bool = True,
        dry_run: bool = False,
    ) -> subprocess.Popen[str] | str:
        """Run a command in a subprocess, with logging and dry-run support."""
        ...


def _run_command(
    command_or_args: Sequence[str] | str,
    /,
    *,
    check: bool = True,
    log_command: bool = True,
    log_output: bool = True,
    capture_output: bool = False,
    dry_run: bool = False,
    **kwargs,
) -> subprocess.Popen[str] | tuple[subprocess.Popen[str], tuple[str, str]] | str:
    """Run a command in a subprocess.

    If `log_command` is True, the command's stdout and stderr outputs are
    written to the log with special prefixes.

    If in "dry run" mode, the command is not executed, and the method returns
    the command string. Otherwise, the subprocess.Popen object is returned. If
    `capture_output` is True, stdout and stderr output are returned as well.

    Parameters
    ----------
    command_or_args : Sequence[str]  |  str
        The command to run.
    check : bool, optional
        If True, raise an error if the process exits with a non-zero code,
        by default True
    log_command : bool, optional
        Whether or not to log the command, by default True
    log_output : bool, optional
        Whether or not to log the command output, by default True
    capture_output : bool, optional
        Whether or not to capture the output, by default False
    dry_run : bool, optional
        If True, do not execute the command, by default False
    **kwargs
        Passed to `subprocess.Popen`.

    Returns
    -------
    subprocess.Popen[str] or tuple[subprocess.Popen[str], tuple[str, str]] or str
        The subprocess.Popen object if the command was executed, or the command
        string if in dry run mode. If `capture_output` is True, a tuple of the
        subprocess.Popen object and a tuple of (stdout, stderr) strings is
        returned.
    """

    def process_output(
        output_source, log_prefix: str, output_list: list, log_level=logging.INFO
    ):
        """Consume lines from an IO stream and log them."""
        for line in output_source:
            line = line.strip("\n")
            if log_output:
                # using extra={"markup": False} in case the output contains substrings
                # that would be interpreted as closing tags by the RichHandler
                logger.log(
                    level=log_level,
                    msg=f"{log_prefix} {line}",
                    extra={"markup": False},
                )
            if output_list is not None:
                output_list.append(line)

    # build command string
    if not isinstance(command_or_args, str):
        args = [str(arg) for arg in command_or_args]
        command = shlex.join(args)
    else:
        command = command_or_args
        args = shlex.split(command)

    # only pass a single string if shell is True
    if not kwargs.get("shell"):
        command_or_args = args

    if log_command:
        _log_command(command)

    if not dry_run:
        process: subprocess.Popen[str] = subprocess.Popen(
            command_or_args,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            **kwargs,
        )

        stdout_list = []
        stderr_list = []
        while process.poll() is None:
            process_output(
                process.stdout,
                LogPrefix.RUN_STDOUT,
                stdout_list,
            )

            process_output(
                process.stderr,
                LogPrefix.RUN_STDERR,
                stderr_list,
                log_level=logging.ERROR,
            )

        if check and process.returncode != 0:
            raise subprocess.CalledProcessError(process.returncode, command)

        if capture_output:
            stdout = "\n".join(stdout_list)
            stderr = "\n".join(stderr_list)
            run_output = (process, (stdout, stderr))
        else:
            run_output = process

    else:
        run_output = command

    return run_output


class BaseWorkflow(Base, ABC):
    """Base workflow class with logging/subprocess/filesystem utilities."""

    def __init__(self, name: str, verbose: bool = False, dry_run: bool = False):
        """Initialize the workflow instance.

        Parameters
        ----------
        name : str
            Name of the workflow, used for logging.
        verbose : bool, optional
            If True, set the logger to DEBUG level, by default False
        dry_run : bool, optional
            If True, print commands without executing them, by default False
        """
        self.name = name
        self.dry_run = dry_run
        self.verbose = verbose

        # for the CLI
        self.return_code = ReturnCode.SUCCESS

        logger.set_verbose(self.verbose)

    def run_setup(self):
        """Run the setup part of the workflow."""
        logger.debug(self)
        if self.dry_run:
            logger.info("Doing a dry run")

    @abstractmethod
    def run_main(self):
        """Run the main part of the workflow."""
        pass

    def run_cleanup(self):
        """Run the cleanup part of the workflow."""
        pass

    def run(self):
        """Run the workflow."""
        try:
            self.run_setup()
            self.run_main()
        except Exception:
            raise
        finally:
            self.run_cleanup()


class BaseDatasetWorkflow(BaseWorkflow, ABC):
    """Base workflow class with awareness of dataset layout and components."""

    def __init__(
        self,
        dpath_root: StrOrPathLike,
        name: str,
        fpath_layout: StrOrPathLike | None = None,
        verbose: bool = False,
        dry_run: bool = False,
        _skip_logfile: bool = False,
        _validate_layout: bool = True,
    ):
        """Initialize the workflow instance.

        Parameters
        ----------
        dpath_root : nipoppy.env.StrOrPathLike
            Path the the root directory of the dataset.
        name : str
            Name of the workflow, used for logging.
        fpath_layout : nipoppy.env.StrOrPathLike, optional
            Path to a custom layout file, by default None
        verbose : bool, optional
            If True, set the logger to DEBUG level, by default False
        dry_run : bool, optional
            If True, print commands without executing them, by default False
        _skip_logfile : bool, optional
            If True, do not write log to file, by default False
        _validate_layout : bool, optional
            If True, validate the layout during setup, by default True
        """
        super().__init__(name=name, verbose=verbose, dry_run=dry_run)

        # `.nipoppy` is not created by default in version 0.3.4 and below
        self.dpath_root = is_nipoppy_project(dpath_root) or Path(dpath_root)
        self.fpath_layout = fpath_layout
        self._skip_logfile = _skip_logfile
        self._validate_layout = _validate_layout

        self.study = Study(
            DatasetLayout(
                dpath_root=self.dpath_root,
                fpath_config=self.fpath_layout,
            )
        )

    def generate_fpath_log(
        self,
        dnames_parent: str | list[str] | None = None,
        fname_stem: str | None = None,
    ) -> Path:
        """Generate a log file path."""
        if dnames_parent is None:
            dnames_parent = []
        if isinstance(dnames_parent, str):
            dnames_parent = [dnames_parent]
        if fname_stem is None:
            fname_stem = self.name
        dpath_log = self.study.layout.dpath_logs / PROGRAM_NAME / self.name
        for dname in dnames_parent:
            dpath_log = dpath_log / dname
        return dpath_log / add_path_timestamp(f"{fname_stem}{EXT_LOG}")

    def run_setup(self):
        """Run the setup part of the workflow."""
        if self._validate_layout:
            self.study.layout.validate()

        if not self._skip_logfile:
            logger.add_file_handler(self.generate_fpath_log())

        super().run_setup()

    @cached_property
    def curation_status_table(self) -> CurationStatusTable:
        """
        Load the curation status file if it exists.

        Otherwise, generate a new one.
        """
        fpath_table = Path(self.study.layout.fpath_curation_status)
        try:
            return self.study.curation_status_table
        except FileNotFoundError:
            logger.warning(
                f"Curation status file not found: {fpath_table}"
                ". Generating a new one on-the-fly"
            )
            table = generate_curation_status_table(
                manifest=self.study.manifest,
                dicom_dir_map=self.dicom_dir_map,
                dpath_downloaded=self.study.layout.dpath_pre_reorg,
                dpath_organized=self.study.layout.dpath_post_reorg,
                dpath_bidsified=self.study.layout.dpath_bids,
            )

            if not self.dry_run:
                table.save_with_backup(fpath_table)
            else:
                logger.info(
                    "Not writing curation status table to "
                    f"{fpath_table} since this is a dry run"
                )

            return table

    @cached_property
    def processing_status_table(self) -> ProcessingStatusTable:
        """
        Load the processing status file it it exists.

        Otherwise, return an empty processing status table.
        """
        try:
            return self.study.processing_status_table
        except FileNotFoundError:
            return ProcessingStatusTable()

    @cached_property
    def dicom_dir_map(self) -> DicomDirMap:
        """Get the DICOM directory mapping."""
        fpath_dicom_dir_map = self.study.config.DICOM_DIR_MAP_FILE
        if fpath_dicom_dir_map is not None and not Path(fpath_dicom_dir_map).exists():
            raise FileOperationError(
                f"DICOM directory map file not found: {fpath_dicom_dir_map}"
            )

        return DicomDirMap.load_or_generate(
            manifest=self.study.manifest,
            fpath_dicom_dir_map=fpath_dicom_dir_map,
            participant_first=self.study.config.DICOM_DIR_PARTICIPANT_FIRST,
        )
