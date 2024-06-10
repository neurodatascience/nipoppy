"""Workflow for convert command."""

from __future__ import annotations

import logging
from functools import cached_property
from pathlib import Path
from typing import Optional

from nipoppy.config.pipeline import PipelineConfig
from nipoppy.utils import StrOrPathLike
from nipoppy.workflows.runner import PipelineRunner


class BidsConversionRunner(PipelineRunner):
    """Convert data to BIDS."""

    def __init__(
        self,
        dpath_root: StrOrPathLike,
        pipeline_name: str,
        pipeline_version: Optional[str] = None,
        pipeline_step: Optional[str] = None,
        participant: str = None,
        session: str = None,
        simulate: bool = False,
        fpath_layout: Optional[StrOrPathLike] = None,
        logger: Optional[logging.Logger] = None,
        dry_run: bool = False,
    ):
        super().__init__(
            dpath_root=dpath_root,
            pipeline_name=pipeline_name,
            pipeline_version=pipeline_version,
            pipeline_step=pipeline_step,
            participant=participant,
            session=session,
            simulate=simulate,
            fpath_layout=fpath_layout,
            logger=logger,
            dry_run=dry_run,
        )
        self.name = "bids_conversion"

    @cached_property
    def dpaths_to_check(self) -> list[Path]:
        """Directory paths to create if needed during the setup phase."""
        # no pipeline-specific directories for BIDS conversion
        return []

    @cached_property
    def pipeline_config(self) -> PipelineConfig:
        """Get the user config for the BIDS conversion software."""
        return self.config.get_pipeline_config(
            self.pipeline_name,
            self.pipeline_version,
        )

    def get_participants_sessions_to_run(
        self, participant: Optional[str], session: Optional[str]
    ):
        """Return participant-session pairs to run the pipeline on."""
        return self.doughnut.get_organized_participants_sessions(
            participant=participant, session=session
        )

    def run_single(self, participant: str, session: str):
        """Run BIDS conversion on a single participant/session."""
        # get container command
        container_command = self.process_container_config(
            participant=participant,
            session=session,
            bind_paths=[
                self.layout.dpath_sourcedata,
                self.layout.dpath_bids,
            ],
        )

        # run pipeline with Boutiques
        self.launch_boutiques_run(
            participant, session, container_command=container_command
        )

        # update status
        self.doughnut.set_status(
            participant=participant,
            session=session,
            col=self.doughnut.col_bidsified,
            status=True,
        )
