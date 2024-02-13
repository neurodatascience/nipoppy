from __future__ import annotations
import copy
import json
import os
from pathlib import Path
from typing import Iterable, Mapping

# TODO decide where to put this (and if this is even needed)
FNAME_MANIFEST = 'manifest.csv'
FNAME_DOUGHNUT = 'doughnut.csv'
FNAME_BAGEL = 'bagel.csv'

class Base():

    def _str_helper(self, components=None, names=None, sep=', '):
        if components is None:
            components = []

        if names is not None:
            for name in names:
                components.append(f'{name}={getattr(self, name)}')
        return f'{type(self).__name__}({sep.join([str(c) for c in components])})'

    def __str__(self) -> str:
        return self._str_helper()

    def __repr__(self) -> str:
        return self.__str__()

class GlobalConfigs(Base):

    class Program(Base):

        def __init__(self, name, config) -> None:
            self.name = name
            self._config = config
            try:
                # required field(s)
                self.version = self._process_version(config['VERSION'])
                self.fname_container_template: str = config['CONTAINER']
            except KeyError as exception:
                self.raise_missing_field_error(exception)

        def _get_optional_field(self, field_name):
            try:
                return self._config[field_name]
            except KeyError as exception:
                self.raise_missing_field_error(exception)

        @property
        def invocation_template(self) -> str:
            return self._get_optional_field('INVOCATION_TEMPLATE')

        def get_fname_container(self, version: str | None = None) -> str:
            version = self.check_version(version)
            return self.fname_container_template.format(version)
        
        def get_fname_pybids_ignore(self, version: str | None = None) -> str:
            version = self.check_version(version)
            # TODO have default? Include in global configs?
            return f'{self.name}-{version}.txt'
        
        def get_fpath_invocation_template(self, version: str | None = None) -> Path:
            version = self.check_version(version)
            fpath_invocation_template = Path(
                self.invocation_template.format(version)
            )
            return fpath_invocation_template

        def _process_version(self, version: str | Iterable[str]):
            if isinstance(version, str):
                version = [version]
            if len(version) == 0:
                if self.name is not None:
                    message_suffix = f' given for pipeline {self.name}'
                else:
                    message_suffix = ''
                raise ValueError(f'No version(s){message_suffix}')
            return version

        def check_version(self, version: str | None):
            if version is None:
                version = self.version[0]
            elif version not in self.version:
                raise RuntimeError(
                    f'Version mismatch for program {self.name}: '
                    f'{version} != {self.version}'
                )
            return version

        def raise_missing_field_error(self, original_exception):
            raise GlobalConfigs.MissingFieldException(
                original_exception,
                message_suffix=f'for program: {self.name}',
            )
        
        def __str__(self) -> str:
            return self._str_helper(names=['name', 'version'])

    def __init__(self, source: GlobalConfigs | dict | os.PathLike | str, validate_root=True) -> None:
        """Load global configs from file."""

        if isinstance(source, GlobalConfigs):
            global_configs_dict = copy.deepcopy(source.global_configs_dict)
        elif isinstance(source, dict):
            global_configs_dict = copy.deepcopy(source)
        elif isinstance(source, (str, os.PathLike)):
            fpath_global_configs = Path(source)
            if not fpath_global_configs.exists():
                raise FileNotFoundError(
                    f'Global configs file does not exist: {fpath_global_configs}'
                )
            with open(fpath_global_configs, 'r') as file_global_configs:
                global_configs_dict = json.load(file_global_configs)
        else:
            raise TypeError(
                f'Expected a dict or a str/path-like object, '
                f'got {type(source)}'
            )

        # TODO use a schema for validation ?
        try:
            self.dataset_name = Path(global_configs_dict['DATASET_NAME'])
            self.dataset_root = Path(global_configs_dict['DATASET_ROOT'])
            self.container_store: str = global_configs_dict['CONTAINER_STORE']
            self.singularity_path: str = global_configs_dict['SINGULARITY_PATH']
            self.sessions: list[str] = global_configs_dict['SESSIONS']
            self.visits: list[str] = global_configs_dict['VISITS']
            self.tabular: dict[str, dict] = global_configs_dict['TABULAR']
            self.workflows: list = global_configs_dict['WORKFLOWS']
            self.programs = self._process_programs(
                global_configs_dict['BIDS'],
                global_configs_dict['PROC_PIPELINES'],
            )
        except KeyError as exception:
            self.raise_missing_field_error(exception)

        self.source = source
        self.global_configs_dict = global_configs_dict

        # TODO add more
        # TODO load tree.json as an object?
        self.dpath_bids = self.dataset_root / 'bids'
        self.dpath_proc = self.dataset_root / 'proc'
        self.dpath_scratch = self.dataset_root / 'scratch'
        self.dpath_raw_dicom = self.dpath_scratch / 'raw_dicom'
        self.dpath_tabular = self.dataset_root / 'tabular'
        self.dpath_derivatives = self.dataset_root / 'derivatives'
        self.dpath_pybids = self.dpath_proc / 'pybids'
        self.dpath_pybids_ignore = self.dpath_pybids / 'ignore_patterns'
        self.fpath_manifest = self.dpath_tabular / FNAME_MANIFEST
        self.fpath_doughnut = self.dpath_raw_dicom / FNAME_DOUGHNUT
        self.fpath_derivatives_bagel = self.dpath_derivatives / FNAME_BAGEL

        if validate_root:
            if not self.dataset_root.exists():
                raise FileNotFoundError(
                    f'Dataset root does not exist: {self.dataset_root}'
                )

    @property
    def templateflow_dir(self) -> Path:
        return Path(self._get_optional_field('TEMPLATEFLOW_DIR'))

    def _get_optional_field(self, field_name):
        try:
            return self.global_configs_dict[field_name]
        except KeyError as exception:
            self.raise_missing_field_error(exception)

    @classmethod
    def _process_programs(cls, *program_configs_all: Mapping[str, Mapping]) -> dict[str, Program]:
        programs = {}
        for program_configs in program_configs_all:
            for name, config in program_configs.items():
                if name in programs:
                    raise RuntimeError(
                        f'Program {name} is not unique'
                    )
                programs[name] = cls.Program(name, config)
        return programs
    
    def get_program(self, program_name: str) -> GlobalConfigs.Program:
        try:
            program = self.programs[program_name]
        except KeyError as exception:
            raise RuntimeError(
                f'Program {exception} not found in global configs. '
                f'Available programs are: {list(self.programs.keys())}'
            )
        return program

    def check_version(self, program_name: str, program_version: str | None = None) -> str:
        return self.get_program(program_name).check_version(program_version)

    def get_dpath_pipeline_derivatives(self, pipeline_name: str, pipeline_version: str | None = None, check_version=True) -> Path:
        if check_version:
            pipeline_version = self.check_version(pipeline_name, pipeline_version)
        return self.dpath_derivatives / pipeline_name / pipeline_version
    
    def get_fpath_container(self, program_name: str, program_version: str | None = None) -> Path:
        program = self.get_program(program_name)
        return Path(self.container_store) / program.get_fname_container(program_version)

    def get_fpath_pybids_ignore(self, programe_name: str, program_version: str | None = None) -> Path:
        program = self.get_program(programe_name)
        return self.dpath_pybids_ignore / program.get_fname_pybids_ignore(program_version)

    def get_fpath_invocation_template(self, program_name: str, program_version: str | None = None) -> Path:
        program = self.get_program(program_name)
        return program.get_fpath_invocation_template(program_version)
    
    class MissingFieldException(Exception):
        def __init__(self, field, message_suffix='') -> None:
            if not message_suffix.startswith(' '):
                message_suffix = f' {message_suffix}'
            self.field = field
            self.message_suffix = message_suffix
            self.message = f'Missing field {field}{message_suffix}'
            super().__init__(self.message)

    def raise_missing_field_error(self, original_exception, message_suffix='from global configs'):
        raise self.MissingFieldException(original_exception, message_suffix=message_suffix)

    def __str__(self) -> str:
        return self._str_helper([self.source])
