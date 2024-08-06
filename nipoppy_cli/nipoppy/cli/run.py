"""Command-line interface."""

import logging
import sys
from typing import Sequence

from rich_argparse import RichHelpFormatter

from nipoppy.cli.parser import (
    COMMAND_BIDS_CONVERSION,
    COMMAND_DICOM_REORG,
    COMMAND_DOUGHNUT,
    COMMAND_INIT,
    COMMAND_PIPELINE_RUN,
    COMMAND_PIPELINE_TRACK,
    get_global_parser,
)
from nipoppy.logger import add_logfile, capture_warnings, get_logger


def cli(argv: Sequence[str] = None) -> None:
    """Entrypoint to the command-line interface."""
    if argv is None:
        argv = sys.argv
    parser = get_global_parser(formatter_class=RichHelpFormatter)
    args = parser.parse_args(argv[1:])

    # common arguments
    command = args.command
    fpath_layout = args.fpath_layout
    logger = get_logger(name=command, level=args.verbosity)
    dry_run = args.dry_run

    # to pass to all workflows
    workflow_kwargs = dict(fpath_layout=fpath_layout, logger=logger, dry_run=dry_run)

    try:
        dpath_root = args.dataset_root

        if command == COMMAND_INIT:
            # Lazy import to improve performance of cli.
            from nipoppy.workflows.dataset_init import InitWorkflow

            workflow = InitWorkflow(
                dpath_root=dpath_root,
                **workflow_kwargs,
            )
        elif command == COMMAND_DOUGHNUT:
            # Lazy import to improve performance of cli.
            from nipoppy.workflows.doughnut import DoughnutWorkflow

            workflow = DoughnutWorkflow(
                dpath_root=dpath_root,
                empty=args.empty,
                regenerate=args.regenerate,
                **workflow_kwargs,
            )
        elif command == COMMAND_DICOM_REORG:
            # Lazy import to improve performance of cli.
            from nipoppy.workflows.dicom_reorg import DicomReorgWorkflow

            workflow = DicomReorgWorkflow(
                dpath_root=dpath_root,
                copy_files=args.copy_files,
                check_dicoms=args.check_dicoms,
                **workflow_kwargs,
            )
        elif command == COMMAND_BIDS_CONVERSION:
            # Lazy import to improve performance of cli.
            from nipoppy.workflows.bids_conversion import BidsConversionRunner

            workflow = BidsConversionRunner(
                dpath_root=dpath_root,
                pipeline_name=args.pipeline,
                pipeline_version=args.pipeline_version,
                pipeline_step=args.pipeline_step,
                participant_id=args.participant_id,
                session_id=args.session_id,
                simulate=args.simulate,
                **workflow_kwargs,
            )
        elif command == COMMAND_PIPELINE_RUN:
            # Lazy import to improve performance of cli.
            from nipoppy.workflows.runner import PipelineRunner

            workflow = PipelineRunner(
                dpath_root=dpath_root,
                pipeline_name=args.pipeline,
                pipeline_version=args.pipeline_version,
                pipeline_step=args.pipeline_step,
                participant_id=args.participant_id,
                session_id=args.session_id,
                simulate=args.simulate,
                **workflow_kwargs,
            )
        elif command == COMMAND_PIPELINE_TRACK:
            # Lazy import to improve performance of cli.
            from nipoppy.workflows.tracker import PipelineTracker

            workflow = PipelineTracker(
                dpath_root=dpath_root,
                pipeline_name=args.pipeline,
                pipeline_version=args.pipeline_version,
                participant_id=args.participant_id,
                session_id=args.session_id,
                **workflow_kwargs,
            )
        else:
            raise ValueError(f"Unsupported command: {command}")

        # cannot log to file in init since the dataset doesn't exist yet
        if command != COMMAND_INIT:
            add_logfile(logger, workflow.generate_fpath_log())

        # capture warnings
        logging.captureWarnings(True)
        capture_warnings(workflow.logger)

        # run the workflow
        workflow.run()

    except Exception:
        logger.exception("Error when creating/running a workflow")
        sys.exit(1)
