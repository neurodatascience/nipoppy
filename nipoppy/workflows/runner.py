"""Abstract class for workflow runners and runner utilities."""

import copy
import json
import shlex
from abc import ABC
from functools import cached_property
from pathlib import Path

from typing_extensions import override

from nipoppy.config.boutiques import BoutiquesConfig
from nipoppy.config.container import ContainerConfig
from nipoppy.config.hpc import HpcConfig
from nipoppy.container import ContainerHandler, get_container_handler
from nipoppy.env import ContainerCommandEnum, StrOrPathLike
from nipoppy.logger import get_logger
from nipoppy.pipeline_validation import check_pipeline_bundle
from nipoppy.utils.utils import TEMPLATE_REPLACE_PATTERN, get_pipeline_tag, load_json
from nipoppy.workflows.base import _run_command
from nipoppy.workflows.pipeline import BasePipelineWorkflow
from nipoppy.workflows.services.boutiques import (
    BoshRunnerCallable,
    run_bosh_launch,
    run_bosh_simulate,
)
from nipoppy.workflows.services.hpc import HPCRunner

logger = get_logger()


class Runner(BasePipelineWorkflow, ABC):
    """Abstract class for workflow runners."""

    # TODO Generic type for pipeline config and pipeline step config attributes

    def __init__(
        self,
        subcommand: str,
        simulate: bool = False,
        keep_workdir: bool = False,
        *args,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self.subcommand = subcommand
        self.simulate = simulate
        self.keep_workdir = keep_workdir

    def run_setup(self):
        """Run pipeline setup and validate the pipeline bundle."""
        to_return = super().run_setup()
        check_pipeline_bundle(self.dpath_pipeline_bundle, strict=False)
        return to_return

    @cached_property
    def hpc_runner(self) -> HPCRunner:
        """Get the HPC runner service."""
        return HPCRunner(
            hpc_cluster=self.hpc,
            hpc_config=self.hpc_config,
            subcommand=self.subcommand,
            dpath_root=self.dpath_root,
            dpath_hpc=self.study.layout.dpath_hpc,
            pipeline_name=self.pipeline_name,
            pipeline_version=self.pipeline_version,
            pipeline_step=self.pipeline_step,
            preamble=self.study.config.HPC_PREAMBLE,
            queue_limit=self.study.config.HPC_QUEUE_LIMIT,
            keep_workdir=self.keep_workdir,
            fpath_layout=self.fpath_layout,
            verbose=self.verbose,
        )

    @cached_property
    def hpc_config(self) -> HpcConfig:
        """Load the pipeline step's HPC configuration."""
        fname_hpc_config = self.pipeline_step_config.HPC_CONFIG_FILE
        if fname_hpc_config is None:
            data = {}
        else:
            fpath_hpc_config = self.dpath_pipeline_bundle / fname_hpc_config
            logger.info(f"Loading HPC config from {fpath_hpc_config}")
            data = self.process_template_json(
                load_json(fpath_hpc_config, allow_json5=True)
            )
        return HpcConfig(**data)

    def _generate_cli_command_for_hpc(
        self, participant_id: str | None = None, session_id: str | None = None
    ) -> list[str]:
        """Generate the CLI command to be run on the HPC cluster."""
        return self.hpc_runner.generate_cli_command(
            participant_id=participant_id,
            session_id=session_id,
        )

    def _submit_hpc_job(self, participants_sessions):
        """Submit jobs to a HPC cluster for processing."""
        # generate the list of nipoppy commands for a shell array
        job_array_commands = []
        participant_ids = []
        session_ids = []
        for participant_id, session_id in participants_sessions:
            command = self._generate_cli_command_for_hpc(
                participant_id=participant_id, session_id=session_id
            )
            job_array_commands.append(shlex.join(command))
            participant_ids.append(participant_id)
            session_ids.append(session_id)

        job_name = get_pipeline_tag(
            pipeline_name=self.pipeline_name,
            pipeline_version=self.pipeline_version,
            pipeline_step=self.pipeline_step,
            participant_id=self.participant_id,
            session_id=self.session_id,
        )

        n_submitted_jobs = self.hpc_runner.submit(
            job_name=job_name,
            job_array_commands=job_array_commands,
            participant_ids=participant_ids,
            session_ids=session_ids,
            dpath_work=self.dpath_pipeline_work,
            dpath_hpc_logs=self.study.layout.dpath_logs / self.dname_hpc_logs,
            fname_hpc_error=self.fname_hpc_error,
            fname_job_script=self.fname_job_script,
            pipeline_name=self.pipeline_name,
            pipeline_version=self.pipeline_version,
            pipeline_step=self.pipeline_step,
            dry_run=self.dry_run,
        )

        # for logging
        self.n_success += n_submitted_jobs
        self.n_total += len(job_array_commands)

    @cached_property
    def bosh_runner(self) -> BoshRunnerCallable:
        """Get the bosh exec command."""
        if self.simulate:
            return run_bosh_simulate
        else:
            return run_bosh_launch

    def _inject_container_image(self, descriptor: dict, uri: str) -> dict:
        descriptor = copy.deepcopy(descriptor)
        scheme, sep, image = uri.partition("://")
        if not sep:
            logger.error(f"Failed to parse CONTAINER_INFO.URI {uri}.")
        else:
            container_type = "docker" if scheme == "docker" else "singularity"
            descriptor["container-image"] = {
                "image": image,
                "type": container_type,
            }
        return descriptor

    def launch_boutiques_run(
        self,
        participant_id: str,
        session_id: str,
        container_handler: ContainerHandler | None = None,
        objs: list | None = None,
        **kwargs,
    ):
        """Launch a pipeline run using Boutiques."""
        bosh_exec_launch_args = ["--no-pull"]

        if self.verbose:
            bosh_exec_launch_args.append("--debug")

        # process the descriptor if it containers Nipoppy-specific placeholder
        # expressions (legacy behaviour)
        if TEMPLATE_REPLACE_PATTERN.search(self.descriptor["command-line"]) is not None:
            logger.info("Processing the JSON descriptor")
            descriptor_str = self.process_template_json(
                self.descriptor,
                participant_id=participant_id,
                session_id=session_id,
                objs=objs,
                **kwargs,
                return_str=True,
            )
        else:
            descriptor = self.descriptor

            # if the descriptor is missing "container-image" but CONTAINER_INFO.URI is
            # set in the pipeline config, inject "container-image" so that the pipeline
            # container will still run in a container
            if (
                descriptor.get("container-image") is None
                and self.pipeline_config.CONTAINER_INFO.URI is not None
            ):
                logger.warning(
                    "Descriptor is missing a 'container-image' field."
                    " Using information from CONTAINER_INFO.URI instead."
                )

                descriptor = self._inject_container_image(
                    descriptor, self.pipeline_config.CONTAINER_INFO.URI
                )

            descriptor_str = json.dumps(descriptor)
            if container_handler is None or descriptor.get("container-image") is None:
                bosh_exec_launch_args.append("--no-container")
            else:
                bosh_exec_launch_args.extend(
                    [
                        "--no-automounts",
                        f"--container-opts={shlex.join(container_handler.args)}",
                    ]
                )
                match container_handler.command:
                    case ContainerCommandEnum.SINGULARITY:
                        bosh_exec_launch_args.extend(
                            [
                                "--imagepath",
                                str(self.fpath_container),
                                "--force-singularity",
                            ]
                        )
                    case ContainerCommandEnum.APPTAINER:
                        bosh_exec_launch_args.extend(
                            [
                                "--imagepath",
                                str(self.fpath_container),
                                "--force-apptainer",
                            ]
                        )
                    case ContainerCommandEnum.DOCKER:
                        bosh_exec_launch_args.append("--force-docker")

        logger.debug(f"Descriptor string: {descriptor_str}")

        # process and validate the invocation
        logger.info("Processing the JSON invocation")
        invocation_str = self.process_template_json(
            self.invocation,
            participant_id=participant_id,
            session_id=session_id,
            objs=objs,
            **kwargs,
            return_str=True,
        )
        logger.debug(f"Invocation string: {invocation_str}")

        # run as a subprocess so that stdout/error are captured in the log
        # by default, this will raise an exception if the command fails
        self.bosh_runner(
            invocation_str=invocation_str,
            descriptor_str=descriptor_str,
            bosh_exec_launch_args=bosh_exec_launch_args,
            run_command=_run_command,
            dry_run=self.dry_run,
        )

        return descriptor_str, invocation_str

    def process_container_config(
        self,
        participant_id: str,
        session_id: str,
        bind_paths: list[StrOrPathLike] | None = None,
    ) -> tuple[str, ContainerHandler]:
        """Update container config and generate container command."""
        if bind_paths is None:
            bind_paths = []

        # always bind the dataset's root directory
        bind_paths = [self.study.layout.dpath_root] + bind_paths

        # get and process container config
        container_config = self.pipeline_step_config.get_container_config()
        container_config = ContainerConfig(
            **self.process_template_json(
                container_config.model_dump(),
                participant_id=participant_id,
                session_id=session_id,
            )
        )
        logger.debug(f"Initial container config: {container_config}")

        # get and process Boutiques config
        boutiques_config = BoutiquesConfig(
            **self.process_template_json(
                self.boutiques_config.model_dump(),
                participant_id=participant_id,
                session_id=session_id,
            )
        )

        # update container config with additional information from Boutiques config
        logger.debug(f"Boutiques config: {boutiques_config}")
        if boutiques_config != BoutiquesConfig():
            logger.debug("Updating container config with config from descriptor")
            container_config.merge(boutiques_config.get_container_config())

        container_handler = get_container_handler(container_config)

        # add bind paths
        for bind_path in bind_paths:
            if Path(bind_path).resolve() != Path.cwd().resolve():
                container_handler.add_bind_arg(bind_path)

        logger.debug(f"Using container handler: {container_handler}")

        container_command = container_handler.get_shell_command(
            subcommand=boutiques_config.CONTAINER_SUBCOMMAND,
        )

        return container_command, container_handler

    @override
    def _handle_execution_strategy(self, participants_sessions):
        """Handle the execution strategy based on the workflow configuration.

        Same as the parent, with HPC submission added as an option if configured.
        """
        if self.write_subcohort is not None:
            self._write_subcohort_to_file(participants_sessions)
        elif self.hpc is not None:
            self._submit_hpc_job(participants_sessions)
        else:
            self._run_locally(participants_sessions)
