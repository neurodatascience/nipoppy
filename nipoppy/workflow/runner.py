from __future__ import annotations
import datetime
import json
import logging
import os
import re
import shlex
import subprocess
import traceback
from abc import ABC, abstractmethod
from functools import wraps, cached_property
from pathlib import Path
from typing import Iterable, Sequence

from nipoppy.base import Base, GlobalConfigs
from nipoppy.io import load_json_as_str
from nipoppy.logger import create_logger
from nipoppy.workflow.utils import BIDS_SESSION_PREFIX, BIDS_SUBJECT_PREFIX

class BaseRunner(Base, ABC):

    sep = '-'
    dname_logs = 'logs'
    template_replace_pattern = re.compile('\\[\\[NIPOPPY\\_(.*?)\\]\\]')
    log_prefix_run = '[RUN]'
    log_prefix_run_stdout = '[RUN STDOUT]'
    log_prefix_run_stderr = '[RUN STDERR]'
    
    def __init__(self, global_configs, name: str, logger=None, log_level=logging.DEBUG, dry_run=False) -> None:

        if not isinstance(global_configs, GlobalConfigs):
            global_configs = GlobalConfigs(global_configs)

        self.global_configs = global_configs
        self.name = name
        self.dry_run = dry_run
        self.logger: logging.Logger | None = logger
        self.log_level = log_level

        self.fpath_log = None
        self.command_failed = False
        self.command_history: list = []

    def log_errors(func):

        @wraps(func)
        def _func(self: BaseRunner, *args, **kwargs):
            try:
                return func(self, *args, **kwargs)
            except Exception as exception:
                self.run_cleanup(**kwargs)
                self.error(traceback.format_exc())
                raise exception

        return _func
    
    @log_errors
    def run(self, **kwargs):
        self.run_setup(**kwargs)
        self.run_main(**kwargs)
        self.run_cleanup(**kwargs)

    def run_setup(self, print_begin=True, **kwargs):
        if print_begin:
            self.info('========== BEGIN ==========')

    @abstractmethod
    def run_main(self, **kwargs):
        pass

    def run_cleanup(self, print_end=True, **kwargs):
        if print_end:
            self.info('========== END ==========')
    
    def process_template_str(self, template_str: str, resolve_paths=True, **kwargs) -> str:

        def replace(json_str: str, to_replace: str, replacement):
            if resolve_paths and isinstance(replacement, Path):
                replacement = replacement.resolve()
            return json_str.replace(to_replace, str(replacement))

        matches = self.template_replace_pattern.finditer(template_str)
        for match in matches:
            if len(match.groups()) != 1:
                raise ValueError(
                    f'Expected exactly one match group for match: {match}'
                )
            to_replace = match.group()
            replacement_key = match.groups()[0].lower()

            if replacement_key in kwargs:
                template_str = replace(template_str, to_replace, kwargs[replacement_key])
            elif hasattr(self, replacement_key):
                template_str = replace(template_str, to_replace, getattr(self, replacement_key))
            elif hasattr(self.global_configs, replacement_key):
                template_str = replace(template_str, to_replace, getattr(self.global_configs, replacement_key))
            else:
                raise RuntimeError(f'Unable to replace {to_replace} in {template_str}')
            
        return template_str
    
    def generate_fpath_log(self, tags=None) -> Path:
        if tags is None:
            tags = []
        elif isinstance(tags, str) or not isinstance(tags, Sequence):
            tags = [tags]
        tags = [str(tag) for tag in tags]
        timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        dpath_log = self.global_configs.dpath_scratch / self.dname_logs / self.name
        fname_log = f'{self.sep.join([self.name, timestamp] + tags)}.log'
        return dpath_log / fname_log

    def run_command(self, command_or_args: Sequence[str] | str, shell=False, check=True, capture_output=False, **kwargs):

        def process_output(output_source: subprocess.IO, output_str: str, log_prefix: str):
            for line in output_source:
                if capture_output:
                    output_str += line # store the line as-is
                line = line.strip('\n')
                self.debug(f'{log_prefix} {line}')
            return output_str
        
        # build command string
        if not isinstance(command_or_args, str):
            args = [str(arg) for arg in command_or_args]
            command = shlex.join(args)
        else:
            command = command_or_args
            args = shlex.split(command)

        # only pass a single string if shell is True
        if not shell:
            command_or_args = args

        self.log_command(command)

        stdout_str = ''
        stderr_str = ''
        if not self.dry_run:

            process = subprocess.Popen(
                command_or_args,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                shell=shell,
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
                )
            
            if check and process.returncode != 0:
                exception = subprocess.CalledProcessError(process.returncode, command)
                self.error(exception)
                self.command_failed = True
                raise exception
            
            run_output = process
            
        else:
            run_output = command

        # return the captured stdout/stderr strings
        # instead of the POpen object or command string
        if capture_output:
            run_output = (stdout_str, stderr_str)

        # only include successful commands in history
        self.command_history.append(command_or_args)

        return run_output
    
    def log_command(self, command: str):
        self.info(f'{self.log_prefix_run} {command}')
    
    def _log(self, message, level=logging.INFO, splitlines=True):
        if self.logger is None:
            if self.fpath_log is None:
                self.fpath_log = self.generate_fpath_log()
            self.logger = create_logger(
                name=str(self),
                fpath=self.fpath_log,
                level=self.log_level,
            )
        if splitlines:
            for line in str(message).splitlines():
                self.logger.log(level, line)
        else:
            self.logger.log(level, message)

    def debug(self, message):
        return self._log(message, level=logging.DEBUG)
    
    def info(self, message):
        return self._log(message, level=logging.INFO)
    
    def warning(self, message):
        return self._log(message, level=logging.WARNING)
    
    def error(self, message):
        return self._log(message, level=logging.ERROR)

    def critical(self, message):
        return self._log(message, level=logging.CRITICAL)

class BaseSingularityRunner(BaseRunner, ABC):

    singularity_cleanenv_flag = '--cleanenv'
    singularity_bind_flag = '--bind'
    singularity_bind_sep = ':'
    singularity_env_prefix = 'APPTAINERENV_'

    envvar_requests_ca_bundle = 'REQUESTS_CA_BUNDLE'
    envvar_templateflow_home = 'TEMPLATEFLOW_HOME'

    def __init__(self, global_configs, name: str, with_templateflow=False, **kwargs) -> None:
        super().__init__(global_configs, name, **kwargs)
        self.with_templateflow = with_templateflow
        self._singularity_flags: list = []

    def run_setup(self, **kwargs):
        output = super().run_setup(**kwargs)
        self.set_singularity_defaults()
        return output
    
    def set_singularity_defaults(self):
        self.add_singularity_flags(self.singularity_cleanenv_flag)
        self.add_singularity_envvar(self.envvar_requests_ca_bundle, '')
        self.setup_templateflow()

    def add_singularity_envvar(self, var_name: str, var_value: str):
        var_name_processed = f'{self.singularity_env_prefix}{var_name}'
        self.info(f'Setting environment variable: {var_name_processed}={var_value}')
        os.environ[var_name_processed] = str(var_value)

    def setup_templateflow(self):
        if self.with_templateflow:
            dpath_templateflow = self.global_configs.templateflow_dir.resolve()
            if not dpath_templateflow.exists():
                raise RuntimeError(
                    f'Templateflow directory now found: {dpath_templateflow}'
                    '. Set with_templateflow to False if it is not needed.'
                )
            self.add_singularity_envvar(
                self.envvar_templateflow_home,
                dpath_templateflow,
            )
            self.add_singularity_symmetric_bind_path(dpath_templateflow)
    
    @property
    def singularity_flags(self) -> str:
        return shlex.join(self._singularity_flags)
    
    def add_singularity_flags(self, flags: str | Iterable) -> None:
        if isinstance(flags, str):
            flags = [flags]
        self._singularity_flags.extend(flags)
    
    def add_singularity_bind_path(self, path_local: str | os.PathLike, path_inside_container: str | os.PathLike | None = None, mode: str = 'rw'):
        
        path_local = Path(path_local).resolve()
        if (not self.dry_run) and (not path_local.exists()):
            raise FileNotFoundError(
                f'Bind path for Apptainer/Singularity does not exist: {path_local}'
            )

        if path_inside_container is None:
            path_inside_container = path_local

        self.add_singularity_flags([
            self.singularity_bind_flag,
            self.singularity_bind_sep.join([
                str(path_local),
                str(path_inside_container),
                mode,
            ])
        ])

    def add_singularity_symmetric_bind_path(self, path: str | os.PathLike, mode='rw'):
        path = Path(path)
        if not path.exists() and mode == 'rw':
            self.warning(
                f'Creating directory because it does not exist: {path}'
                )
            self.run_command(f'mkdir -p {path}')
        self.add_singularity_bind_path(path, mode=mode)

class BoutiquesRunner(BaseSingularityRunner):

    dpath_descriptors = Path(__file__).parent / 'descriptors' # TODO don't hardcode path?
    custom_descriptor_id = 'custom'
    config_descriptor_id = 'nipoppy'

    def __init__(self, global_configs, pipeline_name: str, pipeline_version: str | None = None, **kwargs) -> None:
        global_configs = GlobalConfigs(global_configs)
        pipeline_version = global_configs.check_version(
            pipeline_name,
            pipeline_version,
        )
        name = self.sep.join([pipeline_name, pipeline_version])
        super().__init__(global_configs, name, **kwargs)
        self.pipeline_name = pipeline_name
        self.pipeline_version = pipeline_version

    @cached_property
    def descriptor_template(self) -> str:
        fpath_descriptor_template = self.dpath_descriptors / f'{self.name}.json'
        return load_json_as_str(fpath_descriptor_template)

    @cached_property
    def invocation_template(self) -> str:
        fpath = self.global_configs.get_fpath_invocation_template(
            self.pipeline_name,
            self.pipeline_version,
        )
        return load_json_as_str(fpath)
    
    @cached_property
    def boutiques_config_dict(self) -> dict:
        descriptor_dict = json.loads(self.descriptor_template)
        try:
            config = descriptor_dict[self.custom_descriptor_id][self.config_descriptor_id]
        except (KeyError, TypeError):
            self.warning(f'No custom config object found in Boutiques descriptor for {self.pipeline_name} {self.pipeline_version}')
            return None
        if not isinstance(config, dict):
            raise TypeError(
                f'Expected dict type for custom config object, got: {type(config)}'
            )
        return config

    @cached_property
    def fpath_container(self) -> Path:
        return self.global_configs.get_fpath_container(
            self.pipeline_name,
            self.pipeline_version,
        )

    def run_main(self, **kwargs):

        # process and validate the descriptor
        descriptor = self.process_template_str(self.descriptor_template)
        self.run_command(['bosh', 'validate', descriptor])

        # process and validate the invocation
        invocation = self.process_template_str(
            self.invocation_template,
            **kwargs,
        )
        self.run_command(['bosh', 'invocation', '-i', invocation, descriptor])

        # run
        # self.run_command(['bosh', 'exec', 'simulate', '-i', invocation, descriptor])
        self.run_command(['bosh', 'exec', 'launch', '--stream', descriptor, invocation])
       
    def __str__(self) -> str:
        return self._str_helper([self.pipeline_name, self.pipeline_version])

class ProcpipeRunner(BoutiquesRunner):

    dname_output = 'output'
    dname_work = 'work'
    dname_bids_db_parent = 'bids_db'
    tar_ext = '.tar'
    gzip_ext = '.gz'
    paths_to_tar_descriptor_id = 'paths_to_tar' # for boutiques query

    def __init__(self, global_configs, pipeline_name: str, subject, session, pipeline_version: str | None = None, with_work_dir=True, with_bids_db=True, tar_outputs=False, zip_tar=False, **kwargs) -> None:
        self.subject = str(subject)
        self.session = str(session)
        super().__init__(global_configs=global_configs, pipeline_name=pipeline_name, pipeline_version=pipeline_version, **kwargs)
        self.with_work_dir = with_work_dir 
        self.with_bids_db = with_bids_db
        self.tar_outputs = tar_outputs
        self.zip_tar = zip_tar
        self.layout = None
        self.paths_to_tar = []
        self.bids_ignore_patterns = [ # order matters
            re.compile(rf'^(?!/{BIDS_SUBJECT_PREFIX}({self.subject}))'),
            re.compile(rf'.*?/{BIDS_SESSION_PREFIX}(?!{self.session})'),
        ]

    def generate_fpath_log(self) -> Path:
        return super().generate_fpath_log([self.subject, self.session])
    
    def run_setup(self, **kwargs):

        super().run_setup(**kwargs)

        if self.with_bids_db:
            self.setup_bids_db()

        self.setup_input_directory()
        self.setup_output_directories()

        if self.tar_outputs:
            self.check_paths_to_tar()
        
    def setup_bids_db(self):
        
        # only import when needed
        from bids import BIDSLayout, BIDSLayoutIndexer

        # add more BIDS ignore patterns
        fpath_bids_ignore = self.global_configs.get_fpath_pybids_ignore(
            self.pipeline_name,
            self.pipeline_version,
        )

        if fpath_bids_ignore.exists():
            self.info(f'Using BIDS ignore file: {fpath_bids_ignore}')
            with open(fpath_bids_ignore, 'rt') as file_bids_ignore:
                for line in file_bids_ignore:
                    line = line.strip()
                    if line:
                        self.bids_ignore_patterns.append(re.compile(line))
        else:
            self.warning(f'No BIDS ignore file found at {fpath_bids_ignore}')

        self.info(f'Building BIDSLayout with ignore patterns: {self.bids_ignore_patterns}')
        
        if self.dpath_bids_db.exists():
            self.warning(
                f'Overwriting existing BIDS database directory: {self.dpath_bids_db}'
            )
        
        indexer = BIDSLayoutIndexer(
            validate=False,
            ignore=self.bids_ignore_patterns,
        )
        self.layout = BIDSLayout(
            self.global_configs.dpath_bids.resolve(),
            indexer=indexer,
            database_path=self.dpath_bids_db,
            reset_database=True,
        )

        # list all the files in BIDSLayout
        # since we are selecting for specific a specific subject and
        # session, there should not be too many files
        filenames = self.layout.get(return_type='filename')
        for filename in filenames:
            self.debug(filename)

        if len(filenames) == 0:
            self.warning('BIDS database is empty')

    def setup_input_directory(self):
        self.add_singularity_symmetric_bind_path(
            self.global_configs.dpath_bids,
            mode='ro',
        )

    def setup_output_directories(self):
        self.add_singularity_symmetric_bind_path(self.dpath_output)
        if self.with_work_dir:
            self.add_singularity_symmetric_bind_path(self.dpath_work)
        if self.with_bids_db:
            self.add_singularity_symmetric_bind_path(self.dpath_bids_db)

    def check_paths_to_tar(self):

        # check the Boutiques descriptor for paths to tar
        if self.boutiques_config_dict is not None:
            try:
                self.paths_to_tar.extend([
                    Path(self.process_template_str(path))
                    for path in 
                    self.boutiques_config_dict[self.paths_to_tar_descriptor_id]
                ])
            except KeyError:
                pass

        # raise error if tarring is expected but no paths are found
        if len(self.paths_to_tar) == 0:
            raise ValueError(
                'No path to tar specified for'
                f' {self.pipeline_name} {self.pipeline_version}'
                '. Set tar_outputs to False if it is not needed, or'
                ' specify list of path(s) to tar in a custom property'
                'in the Boutiques descriptor'
            )
        
        self.info(f'Paths to tar (on successful completion): {self.paths_to_tar}')

    def run_cleanup(self, **kwargs):
        
        # cleanup steps if run completed successfully
        if not self.command_failed:

            # delete working directory
            if self.with_work_dir:
                self.run_command(f'rm -rf {self.dpath_work}')

            # tar the results
            if self.tar_outputs:
                self.tar_output_files()

        # always delete temporary BIDS database
        if self.with_bids_db:
            self.run_command(f'rm -rf {self.dpath_bids_db}')

        super().run_cleanup(**kwargs)

    def tar_output_files(self):

        if any([not Path(path).exists() for path in self.paths_to_tar]):
            raise FileNotFoundError(
                f'One or more path to tar does not exist: {self.paths_to_tar}'
            )

        for path in self.paths_to_tar:
            tar_flags = '-cvzf' if self.zip_tar else '-cvf'
            path_tarred = f'{path}{self.tar_ext}'
            if self.zip_tar:
                path_tarred += self.gzip_ext
            self.run_command(f'tar {tar_flags} {path_tarred} -C {Path(path).parent} {path.name}')
            self.run_command(f'rm -rf {path}')
    
    @cached_property
    def fpath_pybids_ignore(self) -> Path:
        return self.global_configs.get_fpath_pybids_ignore(
            self.pipeline_name,
            self.pipeline_version,
        )

    @cached_property
    def dpath_pipeline_derivatives(self) -> Path:
        return self.global_configs.get_dpath_pipeline_derivatives(
            self.pipeline_name, self.pipeline_version
        ).resolve()
    
    @cached_property
    def dpath_output(self) -> Path:
        # TODO allow different options depending on pipeline:
        # - self.dpath_pipeline_derivatives / self.dname_output
        # - self.dpath_pipeline_derivatives / session_id_to_bids_session(self.session)
        # - self.dpath_pipeline_derivatives / participant_id_to_bids_id(self.subject)) / session_id_to_bids_session(self.session)
        return (self.dpath_pipeline_derivatives / self.dname_output).resolve()
    
    @cached_property
    def dpath_work(self) -> Path: 
        subject_session_str = self.sep.join([self.subject, self.session]) 
        return (self.dpath_pipeline_derivatives / self.dname_work / subject_session_str).resolve()

    @cached_property
    def dpath_bids_db(self) -> Path:
        dname_bids_db = self.sep.join([self.pipeline_name, self.pipeline_version, self.subject, self.session])
        return (self.global_configs.dpath_pybids / self.dname_bids_db_parent / dname_bids_db).resolve()

    def __str__(self) -> str:
        return self._str_helper([
            self.pipeline_name,
            self.pipeline_version,
            self.subject,
            self.session,
        ])
