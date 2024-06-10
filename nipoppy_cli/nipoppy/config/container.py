"""Container (i.e., Singularity/Apptainer) configuration model and utility functions."""

import argparse
import logging
import os
import shlex
import shutil
from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field

from nipoppy.logger import get_logger
from nipoppy.utils import StrOrPathLike

# Apptainer
APPTAINER_BIND_FLAG = "--bind"
APPTAINER_BIND_SEP = ":"
APPTAINER_ENVVAR_PREFIXES = ["APPTAINERENV_", "SINGULARITYENV_"]


class ContainerConfig(BaseModel):
    """
    Schema for container configuration.

    Does not include information about the container image.
    """

    COMMAND: str = Field(
        default="apptainer",
        description="Name of or path to Apptainer/Singularity executable",
    )
    ARGS: list[str] = Field(
        default=[],
        description=(
            "Arguments for Apptainer/Singularity call"
            " (to be appended after the subcommand)"
        ),
    )
    ENV_VARS: dict[str, str] = Field(
        default={},
        description=(
            "Environment variables that should be available inside the container"
        ),
    )
    INHERIT: bool = Field(
        default=True,
        description=(
            "Whether this config should inherit from higher-lever container configs."
            " If false, will ignore higher-level configs"
        ),
    )

    model_config = ConfigDict(extra="forbid")

    def add_bind_path(
        self,
        path_local: StrOrPathLike,
        path_inside_container: Optional[StrOrPathLike] = None,
        mode: str = "rw",
    ):
        """Add a bind path."""
        self.ARGS = add_bind_path_to_args(
            self.ARGS,
            path_local=path_local,
            path_inside_container=path_inside_container,
            mode=mode,
        )

    def merge(self, other: Any, overwrite_command=False):
        """
        Combine with another ContainerConfig instance.

        By default this only changes arguments and environment variables, and no
        information is overwritten:
        - Arguments from other are appended to arguments of the current instance
        - Environment variables from other do not overwrite those of the current
        instance

        If overwrite_command is True, the command of the current instance is
        replaced with that of the other instance.
        """
        if not isinstance(other, self.__class__):
            raise TypeError(
                f"Cannot merge {self.__class__} with object of type {type(other)}"
            )

        if overwrite_command:
            self.COMMAND = other.COMMAND

        if self.ARGS != other.ARGS:
            self.ARGS.extend(other.ARGS)

        for env_var, value in other.ENV_VARS.items():
            if env_var not in self.ENV_VARS:
                self.ENV_VARS[env_var] = value

        return self


class ContainerInfo(BaseModel):
    """Schema for container image (i.e., file) information."""

    FILE: Optional[Path] = Field(
        default=None,
        description=(
            "Path to the container associated with the pipeline"
            ", relative to the root directory of the dataset"
        ),
    )
    URI: Optional[str] = Field(
        default=None,
        description="The Docker or Apptainer/Singularity URI for the container",
    )

    model_config = ConfigDict(extra="forbid")


class SchemaWithContainerConfig(BaseModel):
    """To be inherited by configs that have a ContainerConfig sub-config."""

    CONTAINER_CONFIG: ContainerConfig = Field(
        default=ContainerConfig(),
        description="Configuration for running a container",
    )

    def get_container_config(self) -> ContainerConfig:
        """Return the pipeline's ContainerConfig object."""
        return self.CONTAINER_CONFIG


def add_bind_path_to_args(
    args: list[str],
    path_local: StrOrPathLike,
    path_inside_container: Optional[StrOrPathLike] = None,
    mode: Optional[str] = "rw",
):
    """Add a bind path to the container arguments.

    Parameters
    ----------
    args : list[str]
        Existing arguments
    path_local : nipoppy.utils.StrOrPathLike
        Path on disk. If this is a relative path or contains symlinks,
        it will be resolved
    path_inside_container : Optional[nipoppy.utils.StrOrPathLike], optional
        Path inside the container (if None, will be the same as the local path),
        by default None
    mode : str, optional
        Read/write permissions.
        Only used if path_inside_container is given, by default "rw"

    Returns
    -------
    list[str]
        The updated argument list
    """
    path_local = Path(path_local).resolve()

    bind_spec_components = [str(path_local)]
    if path_inside_container is not None:
        bind_spec_components.append(str(path_inside_container))
        if mode is not None:
            bind_spec_components.append(mode)

    args.extend(
        [
            APPTAINER_BIND_FLAG,
            APPTAINER_BIND_SEP.join(bind_spec_components),
        ]
    )
    return args


def check_container_args(
    args: list[str], logger: Optional[logging.Logger] = None
) -> list[str]:
    """Check/fix bind flags in args."""
    if logger is None:
        logger = get_logger("check_container_args")

    # use argparse to parse all the bind flags
    bind_spec_dest = "bind"
    parser = argparse.ArgumentParser(exit_on_error=False)
    parser.add_argument(
        APPTAINER_BIND_FLAG, dest=bind_spec_dest, action="extend", nargs=1
    )

    replacement_map = {}
    try:
        # get all bind arguments
        known_args, _ = parser.parse_known_args(args)
        bind_specs = getattr(known_args, bind_spec_dest)
        if bind_specs is not None:
            for bind_spec in bind_specs:
                # get the local path
                bind_spec: str
                bind_spec_components = bind_spec.split(APPTAINER_BIND_SEP)
                path_local = Path(bind_spec_components[0])
                path_local_original = path_local

                logger.debug(f"Checking container bind spec: {bind_spec}")

                # path must be absolute and exist
                path_local = path_local.resolve()
                if path_local != path_local_original:
                    path_local = path_local.resolve()
                    logger.warning(
                        "Resolving path for container"
                        f": {path_local_original} -> {path_local}"
                    )
                if not path_local.exists():
                    path_local.mkdir(parents=True)
                    logger.warning(
                        "Creating missing directory for container bind path"
                        f": {path_local}"
                    )

                # replace bind spec in args
                if path_local != path_local_original:
                    bind_spec_components[0] = str(path_local)
                    replacement_map[bind_spec] = APPTAINER_BIND_SEP.join(
                        bind_spec_components
                    )

    except Exception as exception:
        raise RuntimeError(
            f"Error parsing {APPTAINER_BIND_FLAG} flags in container"
            f" arguments: {args}. Make sure each flag is followed by a valid spec"
            f" (e.g. {APPTAINER_BIND_FLAG} /path/local:/path/container:rw)"
            f". Exact error was: {type(exception).__name__} {exception}"
        )

    # apply replacements
    args_str = shlex.join(args)
    for to_replace, replacement in replacement_map.items():
        args_str = args_str.replace(to_replace, replacement)

    return shlex.split(args_str)


def check_container_command(command: str) -> str:
    """Check that the command is available (i.e. in PATH)."""
    if not shutil.which(command):
        raise RuntimeError(
            f"Container executable not found: {command}"
            ". Make sure it is installed and in your PATH."
        )
    return command


def prepare_container(
    container_config: ContainerConfig,
    subcommand: str = "run",
    check=True,
    logger: Optional[logging.Logger] = None,
) -> str:
    """Build the command for container and set environment variables.

    Parameters
    ----------
    container_config : ContainerConfig
        Config object
    check : bool, optional
        Whether to validate config components and modify them
        if needed, by default True
    logger : Optional[logging.Logger], optional
        Logger, by default None

    Returns
    -------
    str
        The command string
    """
    command = container_config.COMMAND
    args = container_config.ARGS
    env_vars = container_config.ENV_VARS

    if check:
        command = check_container_command(command)
        args = check_container_args(args, logger=logger)

    set_container_env_vars(env_vars, logger=logger)

    return shlex.join([command, subcommand] + args)


def set_container_env_vars(
    env_vars: dict[str, str], logger: Optional[logging.Logger] = None
) -> None:
    """Set environment variables for the container."""
    if logger is None:
        logger = get_logger("set_container_env_vars")
    for var, value in env_vars.items():
        for prefix in APPTAINER_ENVVAR_PREFIXES:
            var_with_prefix = f"{prefix}{var}"
            logger.info(f"Setting environment variable: {var_with_prefix}={value}")
            os.environ[var_with_prefix] = value
