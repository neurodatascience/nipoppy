import logging
import os
from copy import deepcopy
from pathlib import Path

import pytest
from nipoppy.workflow.runner import BaseSingularityRunner

ENVVAR_PREFIX = 'APPTAINERENV_'

@pytest.fixture(scope='function')
def runner(global_configs_fixture, tmp_path: Path):
    class DummyRunner(BaseSingularityRunner):
        def run_main(self, **kwargs):
            return
    runner = DummyRunner(global_configs_fixture, 'runner', dry_run=True)
    runner.fpath_log = tmp_path / 'runner.log'
    return runner


def test_run_setup(runner: BaseSingularityRunner):
    runner.run_setup()

def test_set_singularity_defaults(runner: BaseSingularityRunner):
    runner.set_singularity_defaults()
    assert '--cleanenv' in runner.singularity_flags
    assert f'{ENVVAR_PREFIX}REQUESTS_CA_BUNDLE' in os.environ


@pytest.mark.parametrize(
    'envvar,value',
    [
        ('VAR1', '1'),
        ('VAR2', 'test'),
        ('var3', ''),
    ],
)
def test_add_singularity_envvar(runner: BaseSingularityRunner, envvar, value):
    runner.add_singularity_envvar(envvar, value)
    assert os.environ[f'{ENVVAR_PREFIX}{envvar}'] == value


@pytest.mark.parametrize('templateflow_dir', ['.', __file__])
def test_setup_templateflow(runner: BaseSingularityRunner, tmp_path: Path, templateflow_dir):
    templateflow_dir = Path(templateflow_dir).resolve()
    runner = deepcopy(runner)
    runner.with_templateflow = True
    runner.global_configs.global_configs_dict['TEMPLATEFLOW_DIR'] = templateflow_dir
    runner.setup_templateflow()
    assert f'{ENVVAR_PREFIX}TEMPLATEFLOW_HOME' in os.environ
    assert runner.singularity_flags == f'--bind {templateflow_dir}:{templateflow_dir}:rw'


def test_setup_templateflow_not_found(runner: BaseSingularityRunner):
    runner = deepcopy(runner)
    runner.with_templateflow = True
    runner.global_configs.global_configs_dict['TEMPLATEFLOW_DIR'] = 'fake_path'
    with pytest.raises(RuntimeError):
        runner.setup_templateflow()


@pytest.mark.parametrize(
    'flags,expected',
    [
        ([], ''),
        (['--flag1', 'arg', '--flag2', 'args'], '--flag1 arg --flag2 args'),
    ]
)
def test_singularity_flags(runner: BaseSingularityRunner, flags, expected):
    runner = deepcopy(runner)
    runner._singularity_flags = flags
    assert runner.singularity_flags == expected


@pytest.mark.parametrize('flags,expected',
    [
        ('--flag', '--flag'),
        (['--flag'], '--flag'),
        (['--flag1', '--flag2'], '--flag1 --flag2'),
    ])
def test_add_singularity_flags(runner: BaseSingularityRunner, flags, expected):
    runner = deepcopy(runner)
    runner.add_singularity_flags(flags)
    assert runner.singularity_flags == expected


@pytest.mark.parametrize('path_local', [Path(__file__).parent, '.'])
@pytest.mark.parametrize('path_container', ['/abc', '/abc/def'])
@pytest.mark.parametrize('mode', ['rw', 'ro'])
def test_add_singularity_bind_path(
        runner: BaseSingularityRunner, path_local, path_container, mode):
    runner = deepcopy(runner)
    runner.add_singularity_bind_path(path_local, path_container, mode=mode)
    # make sure local path is absolute in output
    path_local = Path(path_local).resolve()
    expected_flags = f'--bind {path_local}:{path_container}:{mode}'
    assert runner.singularity_flags == expected_flags


@pytest.mark.parametrize('path_local', [Path(__file__).parent, '.'])
@pytest.mark.parametrize('mode', ['rw', 'ro'])
def test_add_singularity_path_no_path_container(
        runner: BaseSingularityRunner, path_local, mode):
    runner = deepcopy(runner)
    runner.add_singularity_bind_path(path_local, mode=mode)
    path_local = Path(path_local).resolve()
    expected_flags = f'--bind {path_local}:{path_local}:{mode}'
    assert runner.singularity_flags == expected_flags


def test_add_singularity_path_ro_error(runner: BaseSingularityRunner):
    runner = deepcopy(runner)
    runner.dry_run = False  # no error if dry_run
    with pytest.raises(FileNotFoundError):
        runner.add_singularity_bind_path('fake_path', mode='ro')


@pytest.mark.parametrize('path_local', [Path(__file__).parent, '.'])
@pytest.mark.parametrize('mode', ['rw', 'ro'])
def test_add_singularity_symmetric_bind_path(runner: BaseSingularityRunner, path_local, mode):
    runner = deepcopy(runner)
    runner.add_singularity_symmetric_bind_path(path_local, mode)
    path_local = Path(path_local).resolve()
    expected_flags = f'--bind {path_local}:{path_local}:{mode}'
    assert runner.singularity_flags == expected_flags


@pytest.mark.parametrize('path_local_relative', ['abc', 'def/ghi'])
def test_add_singularity_symmetric_bind_path_rw_create(
        runner: BaseSingularityRunner,
        caplog: pytest.LogCaptureFixture,
        tmp_path: Path, path_local_relative,
    ):
    path_local = tmp_path / path_local_relative
    runner = deepcopy(runner)
    runner.dry_run = False
    runner.add_singularity_symmetric_bind_path(path_local)
    path_local = Path(path_local).resolve()
    expected_flags = f'--bind {path_local}:{path_local}:rw'
    assert any([
        (
            record.levelno == logging.WARNING and 
            record.message.startswith('Creating directory')
        )
        for record in caplog.records
    ])
    assert runner.singularity_flags == expected_flags
    assert path_local.exists()
