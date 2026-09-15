"""Workflow for pipeline validate command."""

import warnings
from pathlib import Path

from nipoppy.env import PROGRAM_VERSION, PipelineTypeEnum
from nipoppy.exceptions import FileOperationError, WorkflowError
from nipoppy.layout import DatasetLayout
from nipoppy.logger import get_logger
from nipoppy.pipeline_validation import _load_pipeline_config_file
from nipoppy.utils import fileops
from nipoppy.utils.json5 import update_json5_file
from nipoppy.utils.utils import TEMPLATE_PIPELINE_PATH, load_json
from nipoppy.workflows.base import BaseWorkflow, _run_command

logger = get_logger()


class PipelineCreateWorkflow(BaseWorkflow):
    """Workflow for pipeline validate command."""

    def __init__(
        self,
        pipeline_dir: Path,
        type_: PipelineTypeEnum,
        *,
        source_descriptor: Path | None = None,
        verbose=False,
        dry_run=False,
    ):
        super().__init__(
            name="pipeline_create",
            verbose=verbose,
            dry_run=dry_run,
        )
        self.pipeline_dir = pipeline_dir
        self.type_ = type_
        self.source_descriptor = source_descriptor

    def create_bundle(
        self,
        target: Path,
        type_: PipelineTypeEnum,
        *,
        source_descriptor: Path | None = None,
    ):
        """Create a pipeline bundle."""
        if target.exists():
            raise FileOperationError(
                f"Target directory {target} already exists. "
                "Please remove it or choose a different name.",
            )
        else:
            target.mkdir(parents=True, exist_ok=True)

        source_pipeline_config_path = TEMPLATE_PIPELINE_PATH.joinpath(
            f"config-{type_.value}.json5"
        )

        # the template pipeline only has one step
        pipeline_step_config = _load_pipeline_config_file(
            source_pipeline_config_path, strict=True
        ).get_step_config()

        descriptor_path = target.joinpath(pipeline_step_config.DESCRIPTOR_FILE)
        if source_descriptor is not None:
            process, (stdout, stderr) = _run_command(
                ["bosh", "validate", str(source_descriptor)],
                check=False,
                log_command=False,
                log_output=False,
                capture_output=True,
            )
            if process.returncode != 0:
                raise WorkflowError(
                    f"Error validating the descriptor file {source_descriptor}:"
                    f"\n{stdout}\n{stderr}"
                )
            fileops.copy(source_descriptor, descriptor_path, dry_run=self.dry_run)
        else:
            _run_command(
                ["bosh", "create", str(descriptor_path)],
                check=True,
                log_command=False,
                log_output=False,
            )

        substitutions = {"version": PROGRAM_VERSION}

        invocation_path = target.joinpath(pipeline_step_config.INVOCATION_FILE)
        # copy the 'header' (top-level comments)
        fileops.copy_template(
            TEMPLATE_PIPELINE_PATH.joinpath("invocation_header.txt"),
            invocation_path,
            substitutions=substitutions,
            dry_run=self.dry_run,
        )
        # then append the actual example invocation
        _, (stdout, _) = _run_command(
            ["bosh", "example", str(descriptor_path)],
            check=True,
            log_command=False,
            log_output=False,
            capture_output=True,
        )
        with invocation_path.open("a") as file_invocation:
            file_invocation.write(stdout)

        fileops.copy_template(
            TEMPLATE_PIPELINE_PATH.joinpath(pipeline_step_config.HPC_CONFIG_FILE),
            target.joinpath(pipeline_step_config.HPC_CONFIG_FILE),
            substitutions=substitutions,
            dry_run=self.dry_run,
        )

        dest_pipeline_config_path = target.joinpath(DatasetLayout.fname_pipeline_config)
        fileops.copy_template(
            source_pipeline_config_path,
            dest_pipeline_config_path,
            substitutions=substitutions,
            dry_run=self.dry_run,
        )

        # Populate the config.json using descriptor information
        if source_descriptor is not None:
            descriptor = load_json(source_descriptor)
            updates = [
                (["NAME"], descriptor["name"]),
                (["VERSION"], descriptor["tool-version"]),
            ]

            if "container-image" in descriptor:
                uri = f"docker://{descriptor['container-image']['image']}"

                # replace the pipeline name/version with placeholders
                # to avoid users forgetting to update them when copy-pasting
                uri = uri.replace(descriptor["name"], "[[PIPELINE_NAME]]")
                uri = uri.replace(descriptor["tool-version"], "[[PIPELINE_VERSION]]")
                updates.append((["CONTAINER_INFO", "URI"], uri))

            if not self.dry_run:
                update_json5_file(dest_pipeline_config_path, updates)

        # Only PROCESSING pipelines have a tracker.json file
        if self.type_ == PipelineTypeEnum.PROCESSING:
            fileops.copy_template(
                TEMPLATE_PIPELINE_PATH.joinpath(
                    pipeline_step_config.TRACKER_CONFIG_FILE
                ),
                target.joinpath(pipeline_step_config.TRACKER_CONFIG_FILE),
                substitutions=substitutions,
                dry_run=self.dry_run,
            )

    def run_main(self):
        """Run the main workflow."""
        logger.debug(f"Creating pipeline bundle at {self.pipeline_dir}")
        with warnings.catch_warnings():
            warnings.filterwarnings(
                "ignore", message="Unable to replace .*", category=UserWarning
            )
            self.create_bundle(
                target=self.pipeline_dir,
                type_=self.type_,
                source_descriptor=self.source_descriptor,
            )
        logger.success(f"Pipeline bundle successfully created at {self.pipeline_dir}!")
        logger.warning("Edit the files to customize your pipeline.")
        logger.info(
            "You can run [magenta]nipoppy pipeline validate[/] to check your pipeline"
            " configuration and [magenta]nipoppy pipeline upload[/] to upload it to "
            "Zenodo."
            "\nIt is recommended to test the pipeline with a small dataset "
            "before uploading it to Zenodo."
        )
