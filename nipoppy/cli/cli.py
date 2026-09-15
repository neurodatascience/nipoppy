"""Nipoppy CLI."""

import subprocess
from pathlib import Path

import rich_click as click

try:
    from trogon import tui
except ImportError:
    # Fallback no-op decorator if Trogon isn't installed
    def tui(*args, **kwargs):
        """No-op decorator for Trogon."""

        def decorator(f):
            return f

        return decorator


from nipoppy.cli import exception_handler
from nipoppy.cli.groups import OrderedAliasedGroupWithDotenv
from nipoppy.cli.options import (
    dataset_option,
    dep_params,
    global_options,
    layout_option,
    pipeline_options,
    runners_options,
)
from nipoppy.cli.pipeline_catalog import pipeline
from nipoppy.env import FPATH_USER_CONFIG, PROGRAM_VERSION

click.rich_click.OPTION_GROUPS = {
    "nipoppy *": [
        {
            "name": "Command-specific",
            "options": [
                "--dataset",
                "--pipeline",
                "--pipeline-version",
                "--pipeline-step",
                "--bids-source",
                "--mode",
                "--container-store",
                "--default-config",
                "--copy-files",
                "--check-dicoms",
                "--tar",
                "--query",
                "--size",
                "--zenodo-id",
                "--password-file",
                "--sandbox",
                "--community",
                "--regenerate",
            ],
        },
        {
            "name": "Filtering",
            "options": [
                "--participant-id",
                "--session-id",
                "--use-subcohort",
            ],
        },
        {
            "name": "Parallelization",
            "options": [
                "--hpc",
                "--write-subcohort",
                "--n-jobs",
            ],
        },
        {
            "name": "Troubleshooting",
            "options": [
                "--verbose",
                "--dry-run",
                "--simulate",
                "--keep-workdir",
            ],
        },
        {
            "name": "Miscellaneous",
            "options": [
                "--force",
                "--assume-yes",
                "--layout",
                "--help",
            ],
        },
    ]
}


@tui(command="gui", help="Open the Nipoppy terminal GUI.")
@click.group(
    cls=OrderedAliasedGroupWithDotenv,
    context_settings={"help_option_names": ["-h", "--help"], "show_default": True},
    epilog=(
        "Run 'nipoppy COMMAND --help' for more information on a subcommand.\n\n"
        "Or visit the documentation at https://nipoppy.readthedocs.io"
    ),
)
@click.version_option(version=PROGRAM_VERSION)
def cli():
    """Organize and process neuroimaging-clinical datasets."""


if cli.commands.get("gui") is not None:
    cli.commands["gui"].hidden = True


@cli.command()
@dataset_option
@click.option(
    "--bids-source",
    type=click.Path(exists=True, file_okay=False, path_type=Path, resolve_path=True),
    help="Path to a BIDS dataset to initialize the layout with.",
)
@click.option(
    "--mode",
    type=click.Choice(["copy", "move", "symlink"]),
    default="symlink",
    help=(
        "If using a BIDS source, specify whether to copy, move, or symlink the files."
    ),
)
@click.option(
    "--container-store",
    type=click.Path(exists=True, file_okay=False, path_type=Path, resolve_path=True),
    help="Path to an existing (shared) directory for container images.",
    envvar="NIPOPPY_CONTAINER_STORE",
    show_envvar=True,
)
@click.option(
    "--force",
    "-f",
    is_flag=True,
    help=(
        "Create the dataset even if there are already files present"
        " (may clobber existing files)."
    ),
)
@click.option(
    "--default-config",
    is_flag=True,
    help=f"Force use of the default config file, ignoring any user-level config file defined at {FPATH_USER_CONFIG}.",  # noqa: E501
)
@global_options
@layout_option
def init(**params):
    """Initialize a new dataset."""
    from nipoppy.workflows.dataset_init import InitWorkflow

    params = dep_params(**params)
    with exception_handler(InitWorkflow(**params)) as workflow:
        workflow.run()


@cli.command()
@dataset_option
@click.option(
    "--regenerate",
    is_flag=True,
    help="Regenerate the curation status file even if it already exists.",
    deprecated=(
        "This is now the default/only behaviour,"
        " and this option will be removed in a future release."
    ),
)
@global_options
@layout_option
def track_curation(**params):
    """Create or update a dataset's curation status file."""
    from nipoppy.workflows.track_curation import TrackCurationWorkflow

    params = dep_params(**params)
    with exception_handler(TrackCurationWorkflow(**params)) as workflow:
        workflow.run()


@cli.command()
@dataset_option
@click.option(
    "--copy-files",
    is_flag=True,
    help="Copy files when reorganizing (default: create symlinks).",
)
@click.option(
    "--check-dicoms",
    is_flag=True,
    help=(
        "Read DICOM file headers when reorganizing and check if they have the "
        '"DERIVED" image type (which can be problematic for some BIDS '
        "converters). The paths to the derived DICOMs will be written to the log."
    ),
)
@global_options
@layout_option
def reorg(**params):
    """(Re)organize raw (DICOM) files.

    From ``<NIPOPPY_STUDY_ROOT>/sourcedata/imaging/pre_reorg`` to
    ``<NIPOPPY_STUDY_ROOT>/sourcedata/imaging/post_reorg``
    """
    from nipoppy.workflows.dicom_reorg import DicomReorgWorkflow

    params = dep_params(**params)
    with exception_handler(DicomReorgWorkflow(**params)) as workflow:
        workflow.run()


@cli.command()
@dataset_option
@runners_options
@global_options
@layout_option
def bidsify(**params):
    """Run a BIDS conversion pipeline."""
    from nipoppy.workflows.bids_conversion import BIDSificationRunner

    params = dep_params(**params)
    with exception_handler(BIDSificationRunner(**params)) as workflow:
        workflow.run()


@cli.command()
@dataset_option
@runners_options
@click.option(
    "--tar",
    is_flag=True,
    help=(
        "Archive participant-session-level results into a tarball upon "
        "successful completion. The path to be archived should be specified "
        "in the tracker configuration file."
    ),
)
@global_options
@layout_option
def process(**params):
    """Run a processing pipeline."""
    from nipoppy.workflows.processing_runner import ProcessingRunner

    params = dep_params(**params)
    with exception_handler(ProcessingRunner(**params)) as workflow:
        workflow.run()


@cli.command()
@dataset_option
@pipeline_options
@click.option(
    "--n-jobs",
    type=int,
    default=1,
    help=("Number of parallel workers to use."),
)
@global_options
@layout_option
def track_processing(**params):
    """Track the processing status of a pipeline."""
    from nipoppy.workflows.tracker import PipelineTracker

    params = dep_params(**params)
    with exception_handler(PipelineTracker(**params)) as workflow:
        workflow.run()


@cli.command()
@dataset_option
@runners_options
@global_options
@layout_option
def extract(**params):
    """Extract imaging-derived phenotypes (IDPs) from processed data."""
    from nipoppy.workflows.extractor import ExtractionRunner

    params = dep_params(**params)
    with exception_handler(ExtractionRunner(**params)) as workflow:
        workflow.run()


@cli.command()
@dataset_option
@global_options
@layout_option
def status(**params):
    """Print a summary of the dataset."""
    from nipoppy.workflows.dataset_status import StatusWorkflow

    params = dep_params(**params)
    with exception_handler(StatusWorkflow(**params)) as workflow:
        workflow.run()


######################################
# Command groups from external files #
######################################
cli.add_command(pipeline)


#############
# TUI alias #
#############
def tui_launch():  # pragma: no cover
    """Launch the Nipoppy TUI."""
    subprocess.run(["nipoppy", "gui"])
