"""Workflow for init command."""

import logging
from pathlib import Path
from typing import Optional

from nipoppy.tabular.doughnut import Doughnut, generate_doughnut, update_doughnut
from nipoppy.utils import StrOrPathLike
from nipoppy.workflows.base import BaseWorkflow


class DoughnutWorkflow(BaseWorkflow):
    """Workflow for creating/updating a dataset's doughnut file."""

    def __init__(
        self,
        dpath_root: Path,
        empty: bool = False,
        regenerate: bool = False,
        fpath_layout: Optional[StrOrPathLike] = None,
        logger: Optional[logging.Logger] = None,
        dry_run: bool = False,
    ):
        """Initialize the workflow."""
        super().__init__(
            dpath_root=dpath_root,
            name="doughnut",
            fpath_layout=fpath_layout,
            logger=logger,
            dry_run=dry_run,
        )

        self.empty = empty
        self.regenerate = regenerate

    def run_main(self):
        """Generate/update the dataset's doughnut file."""
        fpath_doughnut = self.layout.fpath_doughnut
        dpath_downloaded = self.layout.dpath_raw_dicom
        dpath_organized = self.layout.dpath_sourcedata
        dpath_bidsified = self.layout.dpath_bids
        empty = self.empty
        logger = self.logger

        if fpath_doughnut.exists() and not self.regenerate:
            old_doughnut = Doughnut.load(fpath_doughnut)
            logger.info(f"Found existing doughnut (shape: {old_doughnut.shape})")
            doughnut = update_doughnut(
                doughnut=old_doughnut,
                manifest=self.manifest,
                dicom_dir_map=self.dicom_dir_map,
                dpath_downloaded=dpath_downloaded,
                dpath_organized=dpath_organized,
                dpath_bidsified=dpath_bidsified,
                empty=empty,
                logger=logger,
            )

        else:
            if self.regenerate:
                logger.info("Regenerating the entire doughnut")
            else:
                logger.info(f"Did not find existing doughnut at {fpath_doughnut}")
            doughnut = generate_doughnut(
                manifest=self.manifest,
                dicom_dir_map=self.dicom_dir_map,
                dpath_downloaded=dpath_downloaded,
                dpath_organized=dpath_organized,
                dpath_bidsified=dpath_bidsified,
                empty=empty,
                logger=logger,
            )

        logger.info(f"New/updated doughnut shape: {doughnut.shape}")
        self.save_tabular_file(doughnut, fpath_doughnut)
