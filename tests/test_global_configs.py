import json
from copy import deepcopy
from pathlib import Path
from typing import Mapping

import pytest

from .conftest import global_configs_file
from nipoppy.base import GlobalConfigs

@pytest.fixture
def global_configs() -> GlobalConfigs:
    return GlobalConfigs(global_configs_file())

@pytest.fixture()
def global_configs_dict(request: pytest.FixtureRequest) -> dict:
    with open(global_configs_file()) as file:
        _global_configs_dict = json.load(file)
    return _global_configs_dict

@pytest.fixture
def global_configs_dict_invalid_root() -> dict:
    with open(global_configs_file()) as file:
        _global_configs_dict = json.load(file)
    _global_configs_dict['DATASET_ROOT'] = 'fake/path'
    return _global_configs_dict

@pytest.fixture
def pipeline_configs_dict() -> dict[str, dict]:
    return {
        'fmriprep': {
            'VERSION': '20.2.7',
            'CONTAINER': 'fmriprep-{}.sif',
            'URL': 'https://fmriprep.org/en/stable/'
        },
        'freesurfer': {
            'VERSION': '6.0.1',
            'CONTAINER': 'fmriprep_{}.sif',
            'URL': 'https://surfer.nmr.mgh.harvard.edu/'
        }
    }

@pytest.fixture
def bids_configs_dict() -> dict[str, dict]:
    return {
        'heudiconv': {
            'VERSION': '0.12.2',    
            'CONTAINER': 'heudiconv_{}.sif',
            'URL': 'https://heudiconv.readthedocs.io/en/latest/'
        },
    }

@pytest.fixture
def program_name_and_config_dict() -> dict:
    return (
        'fmriprep',
        {
            'VERSION': '20.2.7',
            'CONTAINER': 'fmriprep-{}.sif',
            'INVOCATION_TEMPLATE': 'fmriprep-{}.json',
            'URL': 'https://fmriprep.org/en/stable/'
        }
    )

@pytest.fixture
def program(program_name_and_config_dict) -> GlobalConfigs.Program:
    name, config = program_name_and_config_dict
    return GlobalConfigs.Program(name=name, config=config)

@pytest.mark.parametrize(
    'source',
    [
        global_configs_file(),
        str(global_configs_file()),
        GlobalConfigs(global_configs_file()),
    ],
)
def test_init(source):
    assert GlobalConfigs(source)

def test_init_dict(global_configs_dict):
    assert GlobalConfigs(global_configs_dict, validate_root=False)

@pytest.mark.parametrize('source', [1, ['x'], None])
def test_init_invalid_source(source):
    with pytest.raises(TypeError):
        GlobalConfigs(source)

def test_init_not_found():
    with pytest.raises(FileNotFoundError):
        GlobalConfigs('fake_path.json')

def test_init_invalid_root(global_configs_dict_invalid_root):
    with pytest.raises(FileNotFoundError):
        GlobalConfigs(global_configs_dict_invalid_root, validate_root=True)

@pytest.mark.parametrize(
    'attribute_to_check,relative_path',
    [
        ('dataset_root', Path('')),
        ('dpath_proc', Path('proc')),
        ('dpath_scratch', Path('scratch')),
        ('dpath_raw_dicom', Path('scratch', 'raw_dicom')),
        ('dpath_tabular', Path('tabular')),
        ('dpath_derivatives', Path('derivatives')),
        ('dpath_pybids', Path('proc', 'pybids')),
        ('dpath_pybids_ignore', Path('proc', 'pybids', 'ignore_patterns')),
        ('fpath_manifest', Path('tabular', 'manifest.csv')),
        ('fpath_doughnut', Path('scratch', 'raw_dicom', 'doughnut.csv')),
        ('fpath_derivatives_bagel', Path('derivatives', 'bagel.csv')),
    ],
)
def test_paths(global_configs_dict, attribute_to_check, relative_path):
    global_configs = GlobalConfigs(global_configs_dict, validate_root=False)
    expected = global_configs_dict['DATASET_ROOT'] / relative_path
    assert getattr(global_configs, attribute_to_check) == expected

@pytest.mark.parametrize(
    'required_field',
    [
        'DATASET_NAME',
        'DATASET_ROOT',
        'CONTAINER_STORE',
        'SINGULARITY_PATH',
        'SESSIONS',
        'VISITS',
        'BIDS',
        'PROC_PIPELINES',
        'TABULAR',
        'WORKFLOWS',
    ],
)
def test_missing_required_field(required_field, global_configs_dict):

    global_configs_dict = deepcopy(global_configs_dict)
    global_configs_dict.pop(required_field)

    with pytest.raises(GlobalConfigs.MissingFieldException, match='Missing field'):
        GlobalConfigs(global_configs_dict)

@pytest.mark.parametrize('attribute', ['templateflow_dir'])
def test_optional_attribute(global_configs, attribute):
    assert getattr(global_configs, attribute)

@pytest.mark.parametrize('field', ['TEMPLATEFLOW_DIR'])
def test_get_optional_field_missing(global_configs_dict, field):
    global_configs_dict = deepcopy(global_configs_dict)
    global_configs_dict.pop(field)
    global_configs = GlobalConfigs(global_configs_dict, validate_root=False)
    with pytest.raises(GlobalConfigs.MissingFieldException, match=field):
        global_configs._get_optional_field(field)

def test_process_programs(pipeline_configs_dict, bids_configs_dict):
    programs = GlobalConfigs._process_programs(pipeline_configs_dict, bids_configs_dict)
    assert isinstance(programs, Mapping)
    assert len(programs) == len(set(pipeline_configs_dict.keys()) | set(bids_configs_dict.keys()))
    for name, program in programs.items():
        assert isinstance(name, str)
        assert isinstance(program, GlobalConfigs.Program)

def test_process_programs_duplicates(pipeline_configs_dict):
    with pytest.raises(RuntimeError, match='not unique'):
        GlobalConfigs._process_programs(pipeline_configs_dict, pipeline_configs_dict)

@pytest.mark.parametrize('name', ['fmriprep', 'heudiconv'])
def test_get_program(global_configs: GlobalConfigs, name):
    assert global_configs.get_program(name)

def test_get_program_invalid(global_configs: GlobalConfigs):
    with pytest.raises(RuntimeError):
       global_configs.get_program('fake_program_name')

@pytest.mark.parametrize('pipeline', ['fmriprep', 'heudiconv'])
def test_check_version(global_configs: GlobalConfigs, pipeline):
    assert global_configs.check_version(pipeline)

@pytest.mark.parametrize(
        'pipeline,expected',
        [
            ('fmriprep', 'derivatives/fmriprep/20.2.7'),
            ('heudiconv', 'derivatives/heudiconv/0.11.6'),
        ],
    )
def test_get_dpath_pipeline_derivatives(global_configs: GlobalConfigs, pipeline, expected):
    assert global_configs.get_dpath_pipeline_derivatives(pipeline) == Path(expected)

@pytest.mark.parametrize('pipeline', ['fmriprep', 'heudiconv'])
@pytest.mark.parametrize('dpath_container_store', ['/path/to/containers', '/container_store'])
def test_get_fpath_container(global_configs_dict, pipeline, dpath_container_store):
    global_configs_dict = deepcopy(global_configs_dict)
    global_configs_dict['CONTAINER_STORE'] = dpath_container_store
    dpath_container_store = Path(dpath_container_store)
    fpath_container = GlobalConfigs(global_configs_dict).get_fpath_container(pipeline)
    assert dpath_container_store in fpath_container.parents

@pytest.mark.parametrize('pipeline', ['fmriprep', 'mriqc'])
def test_get_fpath_bids_ignore(global_configs: GlobalConfigs, pipeline):
    assert global_configs.get_fpath_pybids_ignore(pipeline)

@pytest.mark.parametrize('pipeline', ['fmriprep', 'heudiconv'])
def test_get_fpath_invocation_template(global_configs: GlobalConfigs, pipeline):
    assert global_configs.get_fpath_invocation_template(pipeline)

@pytest.mark.parametrize('exception', [KeyError('x'), 'y'])
@pytest.mark.parametrize('message_suffix', ['suffix1', 'suffix2'])
def test_raise_missing_field_error(global_configs: GlobalConfigs, exception, message_suffix):
    with pytest.raises(GlobalConfigs.MissingFieldException, match=message_suffix):
        global_configs.raise_missing_field_error(exception, message_suffix=message_suffix)

def test_program_init(program_name_and_config_dict):
    name, config = program_name_and_config_dict
    program = GlobalConfigs.Program(name=name, config=config)
    assert program.name == name

@pytest.mark.parametrize('required_field', ['VERSION', 'CONTAINER'])
def test_program_init_missing_required_field(program_name_and_config_dict, required_field):
    name, config = program_name_and_config_dict
    config: dict = config.copy()
    config.pop(required_field)
    with pytest.raises(GlobalConfigs.MissingFieldException, match=required_field):
        GlobalConfigs.Program(name=name, config=config)

@pytest.mark.parametrize('attribute', ['invocation_template'])
def test_program_optional_attribute(program, attribute):
    assert getattr(program, attribute)

@pytest.mark.parametrize('field', ['INVOCATION_TEMPLATE', 'URL'])
def test_program_get_optional_field(program_name_and_config_dict, field):
    name, config = program_name_and_config_dict
    program = GlobalConfigs.Program(name=name, config=config)
    assert program._get_optional_field(field) == config[field]

@pytest.mark.parametrize('field', ['INVOCATION_TEMPLATE', 'URL'])
def test_program_get_optional_field_missing(program_name_and_config_dict, field):
    name, config = program_name_and_config_dict
    config: dict = config.copy()
    config.pop(field)
    program = GlobalConfigs.Program(name=name, config=config)
    with pytest.raises(GlobalConfigs.MissingFieldException, match=field):
        program._get_optional_field(field)

@pytest.mark.parametrize(
    'container,version,expected',
    [
        ('fmriprep-{}.sif', '1.0.0', 'fmriprep-1.0.0.sif'),
        ('fmriprep-{}.sif', None, 'fmriprep-.sif'),
        ('fmriprep.sif', '1.0.0', 'fmriprep.sif'),
        ('fmriprep.sif', None, 'fmriprep.sif'),
    ]
)
def test_program_get_fname_container(program_name_and_config_dict, container, version, expected):
    name, config = program_name_and_config_dict
    config: dict = config.copy()
    config['CONTAINER'] = container
    if version is not None:
        config['VERSION'] = version
    else:
        config['VERSION'] = ''
    program = GlobalConfigs.Program(name=name, config=config)
    assert program.get_fname_container() == expected

@pytest.mark.parametrize('version', ['1.0.0', '20.2.7'])
def test_program_get_fname_pybids_ignore(program_name_and_config_dict, version):
    name, config = program_name_and_config_dict
    config: dict = config.copy()
    config['VERSION'] = version
    program = GlobalConfigs.Program(name=name, config=config)
    assert program.get_fname_pybids_ignore() == f'fmriprep-{version}.txt'

@pytest.mark.parametrize(
    'invocation_template,version,expected',
    [
        ('fmriprep-{}.json', '1.0.0', Path('fmriprep-1.0.0.json')),
        ('fmriprep-{}.json', None, Path('fmriprep-.json')),
        ('fmriprep.json', '1.0.0', Path('fmriprep.json')),
        ('fmriprep.json', None, Path('fmriprep.json')),
    ]
)
def test_program_get_fpath_invocation_template(program_name_and_config_dict, invocation_template, version, expected):
    name, config = program_name_and_config_dict
    config: dict = config.copy()
    config['INVOCATION_TEMPLATE'] = invocation_template
    if version is not None:
        config['VERSION'] = version
    else:
        config['VERSION'] = ''
    program = GlobalConfigs.Program(name=name, config=config)
    assert program.get_fpath_invocation_template() == expected

@pytest.mark.parametrize('version', ['1.0.0', ['1.2.3', '2.0.0']])
@pytest.mark.parametrize('name', ['heudiconv', None])
def test_program_process_version(program: GlobalConfigs.Program, version, name):
    assert program._process_version(version)

def test_program_process_version_empty_list(program: GlobalConfigs.Program):
    with pytest.raises(ValueError):
        program._process_version([])

@pytest.mark.parametrize(
        'version_config,program_version,expected',
        [
            ('1.0.0', None, '1.0.0'),
            ('1.0.1', '1.0.1', '1.0.1'),
            (['2.2.2', '1.0.1'], None, '2.2.2'),
            (['2.3.4', '5.6.7'], '5.6.7', '5.6.7'),
        ]
    )
def test_program_check_version(program_name_and_config_dict, version_config, program_version, expected):
    name, config = program_name_and_config_dict
    config: dict = config.copy()
    config['VERSION'] = version_config
    program = GlobalConfigs.Program(name=name, config=config)
    assert program.check_version(program_version) == expected

def test_program_check_version_error(program: GlobalConfigs.Program):
    with pytest.raises(RuntimeError):
        program.check_version('fake_version')

@pytest.mark.parametrize('exception', [KeyError('xyz'), '123'])
def test_program_raise_missing_field_error(program: GlobalConfigs.Program, exception):
    with pytest.raises(GlobalConfigs.MissingFieldException, match=program.name):
        program.raise_missing_field_error(exception)
