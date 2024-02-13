import json
from pathlib import Path

import pytest
from nipoppy.workflow.runner import BoutiquesRunner

from .conftest import global_configs_for_testing

@pytest.fixture()
def global_configs_dict(tmp_path: Path):
    global_configs = global_configs_for_testing(tmp_path)
    
    # dpath_container = tmp_path / 'containers'
    # dpath_container.mkdir(exist_ok=True)
    # for fname_fake_container in ['fmriprep_20.2.7.sif', 'fmriprep_23.1.3.sif', 'mriqc_23.1.0.sif']:
    #     (dpath_container / fname_fake_container).touch()
    # global_configs['CONTAINER_STORE'] = dpath_container
    
    dpath_invocations = tmp_path / 'invocations'
    dpath_invocations.mkdir(exist_ok=True)
    for fname_fake_invocation in ['fmriprep-20.2.7.json', 'fmriprep-23.1.3.json', 'mriqc-23.1.0.json']:
        fpath_fake_invocation = dpath_invocations / fname_fake_invocation
        with fpath_fake_invocation.open('w') as file_invocation:
            json.dump({}, file_invocation)
    
    global_configs['PROC_PIPELINES'] = {
        "fmriprep": {
            "VERSION": ["20.2.7", "23.1.3"],
            "CONTAINER": "fmriprep_{}.sif",
            "INVOCATION_TEMPLATE": str(dpath_invocations / "fmriprep-{}.json")
        },
        "mriqc": {
            "VERSION": "23.1.0",
            "CONTAINER": "mriqc_{}.sif",
            "INVOCATION_TEMPLATE": str(dpath_invocations / "mriqc-{}.json")
        },
    }
    return global_configs

@pytest.mark.parametrize(
    'pipeline_name,pipeline_version,expected_version,expected_name',
    [
        ('fmriprep', '20.2.7', '20.2.7', 'fmriprep-20.2.7'),
        ('fmriprep', '23.1.3', '23.1.3', 'fmriprep-23.1.3'),
        ('fmriprep', None, '20.2.7', 'fmriprep-20.2.7'),
        ('mriqc', '23.1.0', '23.1.0', 'mriqc-23.1.0'),
        ('mriqc', None, '23.1.0', 'mriqc-23.1.0'),
    ],
)
def test_init(global_configs_dict: dict, pipeline_name, pipeline_version, expected_version, expected_name):
    runner = BoutiquesRunner(global_configs_dict, pipeline_name, pipeline_version)
    assert runner.pipeline_name == pipeline_name
    assert runner.pipeline_version == expected_version
    assert runner.name == expected_name

@pytest.mark.parametrize(
    'pipeline_name,pipeline_version',
    [
        ('fmriprep', '20.2.7'),
        ('fmriprep', '23.1.3'),
        ('mriqc', '23.1.0'),
    ],
)
def test_descriptor_template(global_configs_dict: dict, pipeline_name, pipeline_version):
    runner = BoutiquesRunner(global_configs_dict, pipeline_name, pipeline_version)
    assert isinstance(runner.descriptor_template, str)

@pytest.mark.parametrize(
    'pipeline_name,pipeline_version',
    [
        ('fmriprep', '20.2.7'),
        ('fmriprep', '23.1.3'),
        ('mriqc', '23.1.0'),
    ],
)
def test_invocation_template(global_configs_dict: dict, pipeline_name, pipeline_version):
    runner = BoutiquesRunner(global_configs_dict, pipeline_name, pipeline_version)
    assert isinstance(runner.invocation_template, str)

@pytest.mark.parametrize(
    'pipeline_name,pipeline_version,expect_warning',
    [
        ('fmriprep', '20.2.7', False),
        ('fmriprep', '23.1.3', False),
        ('mriqc', '23.1.0', True),
    ],
)
def test_boutiques_config_dict(global_configs_dict: dict, pipeline_name, pipeline_version, expect_warning, caplog: pytest.LogCaptureFixture):
    runner = BoutiquesRunner(global_configs_dict, pipeline_name, pipeline_version)
    if expect_warning:
        assert runner.boutiques_config_dict is None
        log_record = caplog.records[-1]
        assert log_record.levelname == 'WARNING'
        assert log_record.message.startswith('No custom config object found')
    else:
        assert isinstance(runner.boutiques_config_dict, dict)

@pytest.mark.parametrize(
    'pipeline_name,pipeline_version',
    [
        ('fmriprep', '20.2.7'),
        ('fmriprep', '23.1.3'),
        ('mriqc', '23.1.0'),
    ],
)
def test_fpath_container(global_configs_dict: dict, pipeline_name, pipeline_version):
    runner = BoutiquesRunner(global_configs_dict, pipeline_name, pipeline_version)
    assert isinstance(runner.fpath_container, Path)

def test_run_main(global_configs_dict: dict):
    runner = BoutiquesRunner(global_configs_dict, 'mriqc', dry_run=True)
    
    # define dummy values for these attributes (required by MRIQC descriptor)
    runner.dpath_output = 'fake_dpath_output'
    runner.dpath_work = 'fake_dpath_work'
    runner.dpath_bids_db = 'fake_dpath_bids_db'

    runner.run_main()
    assert runner.command_history[-3][:2] == ['bosh', 'validate']
    assert runner.command_history[-2][:3] == ['bosh', 'invocation', '-i']
    assert runner.command_history[-1][:4] == ['bosh', 'exec', 'launch', '--stream']
