"""Workflow utilities."""

from __future__ import annotations

import json
import logging
import os
import shlex
import shutil
import subprocess
from abc import ABC, abstractmethod
from functools import cached_property
from pathlib import Path
from typing import Optional, Sequence

from nipoppy.base import Base
from nipoppy.config.main import Config
from nipoppy.layout import DatasetLayout
from nipoppy.logger import get_logger
from nipoppy.tabular.base import BaseTabular
from nipoppy.tabular.dicom_dir_map import DicomDirMap
from nipoppy.tabular.doughnut import Doughnut, generate_doughnut
from nipoppy.tabular.manifest import Manifest
from nipoppy.utils import StrOrPathLike, add_path_timestamp, process_template_str

LOG_SUFFIX = ".log"


class BaseWorkflow(Base, ABC):
    """Base class with logging/subprocess utilities."""

    path_sep = "-"
    log_prefix_run = "[RUN]"
    log_prefix_run_stdout = "[RUN STDOUT]"
    log_prefix_run_stderr = "[RUN STDERR]"
    validate_layout = True

    # hack to avoid errors when loading/processing the default config
    pipeline_name = "[[NIPOPPY_PIPELINE_NAME]]"
    pipeline_version = "[[NIPOPPY_PIPELINE_VERSION]]"

    def __init__(
        self,
        dpath_root: StrOrPathLike,
        name: str,
        fpath_layout: Optional[StrOrPathLike] = None,
        logger: Optional[logging.Logger] = None,
        dry_run=False,
    ):
        """Initialize the workflow instance.

        Parameters
        ----------
        dpath_root : nipoppy.utils.StrOrPathLike
            Path the the root directory of the dataset.
        name : str
            Name of the workflow, used for logging.
        logger : logging.Logger, optional
            Logger, by default None
        dry_run : bool, optional
            If True, print commands without executing them, by default False
        """
        if logger is None:
            logger = get_logger(name=name)

        self.dpath_root = Path(dpath_root)
        self.name = name
        self.fpath_layout = fpath_layout
        self.logger = logger
        self.dry_run = dry_run

        self.layout = DatasetLayout(dpath_root=dpath_root, fpath_config=fpath_layout)

    def generate_fpath_log(
        self,
        dnames_parent: Optional[str | list[str]] = None,
        fname_stem: Optional[str] = None,
    ) -> Path:
        """Generate a log file path."""
        if dnames_parent is None:
            dnames_parent = []
        if isinstance(dnames_parent, str):
            dnames_parent = [dnames_parent]
        if fname_stem is None:
            fname_stem = self.name
        dpath_log = self.layout.dpath_logs / self.name
        for dname in dnames_parent:
            dpath_log = dpath_log / dname
        return dpath_log / add_path_timestamp(f"{fname_stem}{LOG_SUFFIX}")

    def log_command(self, command: str):
        """Write a command to the log with a special prefix."""
        self.logger.info(f"{self.log_prefix_run} {command}")

    def run_command(
        self,
        command_or_args: Sequence[str] | str,
        check=True,
        **kwargs,
    ) -> subprocess.Popen | str:
        """Run a command in a subprocess.

        The command's stdout and stderr outputs are written to the log
        with special prefixes.

        If in "dry run" mode, the command is not executed, and the method returns
        the command string. Otherwise, the subprocess.Popen object is returned
        unless capture_output is True.

        Parameters
        ----------
        command_or_args : Sequence[str]  |  str
            The command to run.
        check : bool, optional
            If True, raise an error if the process exits with a non-zero code,
            by default True
        **kwargs
            Passed to `subprocess.Popen`.

        Returns
        -------
        subprocess.Popen or str
        """

        def process_output(
            output_source, output_str: str, log_prefix: str, log_level=logging.INFO
        ):
            """Consume lines from an IO stream and append them to a string."""
            for line in output_source:
                line = line.strip("\n")
                self.logger.log(level=log_level, msg=f"{log_prefix} {line}")
            return output_str

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

        self.log_command(command)

        stdout_str = ""
        stderr_str = ""
        if not self.dry_run:
            process = subprocess.Popen(
                command_or_args,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                **kwargs,
            )

            while process.poll() is None:
                stdout_str = process_output(
                    process.stdout,
                    stdout_str,
                    self.log_prefix_run_stdout,
                )

                stderr_str = process_output(
                    process.stderr,
                    stderr_str,
                    self.log_prefix_run_stderr,
                    log_level=logging.ERROR,
                )

            if check and process.returncode != 0:
                exception = subprocess.CalledProcessError(process.returncode, command)
                raise exception

            run_output = process

        else:
            run_output = command

        return run_output

    def save_tabular_file(self, tabular: BaseTabular, fpath: Path):
        """Save a tabular file."""
        fpath_backup = tabular.save_with_backup(fpath, dry_run=self.dry_run)
        if fpath_backup is not None:
            self.logger.info(f"Saved to {fpath} (-> {fpath_backup})")
        else:
            self.logger.info(f"No changes to file at {fpath}")

    def run_setup(self, **kwargs):
        """Run the setup part of the workflow."""
        self.logger.info(f"========== BEGIN {self.name.upper()} WORKFLOW ==========")
        self.logger.info(self)
        if self.dry_run:
            self.logger.info("Doing a dry run")
        if self.validate_layout:
            try:
                self.layout.validate()
            except FileNotFoundError as exception:
                raise RuntimeError(
                    f"Dataset does not follow expected directory structure: {exception}"
                )

    @abstractmethod
    def run_main(self, **kwargs):
        """Run the main part of the workflow."""
        pass

    def run_cleanup(self, **kwargs):
        """Run the cleanup part of the workflow."""
        self.logger.info(f"========== END {self.name.upper()} WORKFLOW ==========")

    def run(self, **kwargs):
        """Run the workflow."""
        self.run_setup(**kwargs)
        self.run_main(**kwargs)
        self.run_cleanup(**kwargs)

    def mkdir(self, dpath, log_level=logging.INFO, **kwargs):
        """
        Create a directory (by default including parents).

        Do nothing if the directory already exists.
        """
        kwargs_to_use = {"parents": True, "exist_ok": True}
        kwargs_to_use.update(kwargs)

        dpath = Path(dpath)

        if not dpath.exists():
            self.logger.log(level=log_level, msg=f"Creating directory {dpath}")
            if not self.dry_run:
                dpath.mkdir(**kwargs_to_use)
        elif not dpath.is_dir():
            raise FileExistsError(
                f"Path already exists but is not a directory: {dpath}"
            )

    def copy(self, path_source, path_dest, log_level=logging.INFO, **kwargs):
        """Copy a file or directory."""
        self.logger.log(level=log_level, msg=f"Copying {path_source} to {path_dest}")
        if not self.dry_run:
            shutil.copy2(src=path_source, dst=path_dest, **kwargs)

    def create_symlink(self, path_source, path_dest, log_level=logging.INFO, **kwargs):
        """Create a symlink to another path."""
        self.logger.log(
            level=log_level,
            msg=f"Creating a symlink from {path_source} to {path_dest}",
        )
        if not self.dry_run:
            os.symlink(path_source, path_dest, **kwargs)

    def rm(self, path, log_level=logging.INFO, **kwargs):
        """Remove a file or directory."""
        kwargs_to_use = {"ignore_errors": True}
        kwargs_to_use.update(kwargs)
        self.logger.log(level=log_level, msg=f"Removing {path}")
        if not self.dry_run:
            shutil.rmtree(path, **kwargs_to_use)

    @cached_property
    def config(self) -> Config:
        """Load the configuration."""
        fpath_config = self.layout.fpath_config
        try:
            # load and apply user-defined substitutions
            self.logger.info(f"Loading config from {fpath_config}")
            config = Config.load(fpath_config)
        except FileNotFoundError:
            raise FileNotFoundError(
                f"Config file not found: {self.layout.fpath_config}"
            )

        # replace path placeholders in the config
        config = Config(
            **json.loads(
                process_template_str(
                    config.model_dump_json(),
                    objs=[self, self.layout],
                )
            )
        )

        config.propagate_container_config()

        return config

    @cached_property
    def manifest(self) -> Manifest:
        """Load the manifest."""
        fpath_manifest = Path(self.layout.fpath_manifest)
        expected_sessions = self.config.SESSIONS
        expected_visits = self.config.VISITS
        try:
            return Manifest.load(
                fpath_manifest,
                sessions=expected_sessions,
                visits=expected_visits,
            )
        except FileNotFoundError:
            raise FileNotFoundError(f"Manifest file not found: {fpath_manifest}")

    @cached_property
    def doughnut(self) -> Doughnut:
        """Load the doughnut."""
        logger = self.logger
        fpath_doughnut = Path(self.layout.fpath_doughnut)
        try:
            return Doughnut.load(fpath_doughnut)
        except FileNotFoundError:
            self.logger.warning(
                f"Doughnut file not found: {fpath_doughnut}"
                ". Generating a new one on-the-fly"
            )
            doughnut = generate_doughnut(
                manifest=self.manifest,
                dicom_dir_map=self.dicom_dir_map,
                dpath_downloaded=self.layout.dpath_raw_dicom,
                dpath_organized=self.layout.dpath_sourcedata,
                dpath_bidsified=self.layout.dpath_bids,
                empty=False,
                logger=self.logger,
            )

            if not self.dry_run:
                fpath_doughnut_backup = doughnut.save_with_backup(fpath_doughnut)
                logger.info(
                    f"Saved doughnut to {fpath_doughnut} (-> {fpath_doughnut_backup})"
                )
            else:
                logger.info(
                    f"Not writing doughnut to {fpath_doughnut} since this is a dry run"
                )

            return doughnut

    @cached_property
    def dicom_dir_map(self) -> DicomDirMap:
        """Get the DICOM directory mapping."""
        fpath_dicom_dir_map = self.config.DICOM_DIR_MAP_FILE
        if fpath_dicom_dir_map is not None:
            fpath_dicom_dir_map = Path(fpath_dicom_dir_map)
            if not fpath_dicom_dir_map.exists():
                raise FileNotFoundError(
                    "DICOM directory map file not found"
                    f": {self.config.DICOM_DIR_MAP_FILE}"
                )

        return DicomDirMap.load_or_generate(
            manifest=self.manifest,
            fpath_dicom_dir_map=fpath_dicom_dir_map,
            participant_first=self.config.DICOM_DIR_PARTICIPANT_FIRST,
        )
