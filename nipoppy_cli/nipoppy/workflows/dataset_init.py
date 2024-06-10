"""Workflow for init command."""

import logging
from pathlib import Path
from typing import Optional

from nipoppy.utils import (
    DPATH_DESCRIPTORS,
    DPATH_INVOCATIONS,
    DPATH_TRACKER_CONFIGS,
    FPATH_SAMPLE_CONFIG,
    FPATH_SAMPLE_MANIFEST,
    StrOrPathLike,
)
from nipoppy.workflows.base import BaseWorkflow


class InitWorkflow(BaseWorkflow):
    """Workflow for init command."""

    # do not validate since the dataset has not been created yet
    validate_layout = False

    def __init__(
        self,
        dpath_root: Path,
        fpath_layout: Optional[StrOrPathLike] = None,
        logger: Optional[logging.Logger] = None,
        dry_run: bool = False,
    ):
        """Initialize the workflow."""
        super().__init__(
            dpath_root=dpath_root,
            name="init",
            fpath_layout=fpath_layout,
            logger=logger,
            dry_run=dry_run,
        )
        self.fname_readme = "README.md"

    def run_main(self):
        """Create dataset directory structure."""
        # dataset must not already exist
        if self.dpath_root.exists():
            raise FileExistsError("Dataset directory already exists")

        # create directories
        for dpath in self.layout.dpaths:
            self.mkdir(dpath)

        for dpath, description in self.layout.dpath_descriptions:
            fpath_readme = dpath / self.fname_readme
            if description is not None and not self.dry_run:
                fpath_readme.write_text(f"{description}\n")

        self.logger.info(f"Created an empty dataset at {self.dpath_root}")

        # copy descriptor files
        for fpath_descriptor in DPATH_DESCRIPTORS.iterdir():
            self.copy(
                fpath_descriptor,
                self.layout.dpath_descriptors / fpath_descriptor.name,
                log_level=logging.DEBUG,
            )

        # copy sample invocation files
        for fpath_invocation in DPATH_INVOCATIONS.iterdir():
            self.copy(
                fpath_invocation,
                self.layout.dpath_invocations / fpath_invocation.name,
                log_level=logging.DEBUG,
            )

        # copy sample tracker config files
        for fpath_tracker_config in DPATH_TRACKER_CONFIGS.iterdir():
            self.copy(
                fpath_tracker_config,
                self.layout.dpath_tracker_configs / fpath_tracker_config.name,
                log_level=logging.DEBUG,
            )

        # copy sample config and manifest files
        self.copy(
            FPATH_SAMPLE_CONFIG, self.layout.fpath_config, log_level=logging.DEBUG
        )
        self.copy(
            FPATH_SAMPLE_MANIFEST, self.layout.fpath_manifest, log_level=logging.DEBUG
        )

        # inform user to edit the sample files
        self.logger.warning(
            f"Sample config and manifest files copied to {self.layout.fpath_config}"
            f" and {self.layout.fpath_manifest} respectively. They should be edited"
            " to match your dataset"
        )

    @property
    def config(self):
        """Raise an error because the dataset/config file does not yet exist."""
        raise RuntimeError(
            "The config property (and any other that require loading the config)"
            " is not available in this workflow since the dataset does not exist yet"
            " (and so does not have an associated with a config file)"
        )
