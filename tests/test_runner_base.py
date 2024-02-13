import logging
import re
import subprocess
from pathlib import Path

import pytest
from nipoppy.workflow.runner import BaseRunner

@pytest.fixture(scope='function')
def runner(global_configs_fixture, tmp_path: Path):
    class DummyRunner(BaseRunner):
        def run_main(self, **kwargs):
            return
    runner = DummyRunner(global_configs_fixture, 'runner', dry_run=True)
    runner.fpath_log = tmp_path / runner.generate_fpath_log().name
    return runner

def test_abstract_class():
    with pytest.raises(TypeError, match='Can\'t instantiate abstract class'):
        BaseRunner(None, None)

def test_log_errors(runner: BaseRunner, caplog: pytest.LogCaptureFixture):
    
    @BaseRunner.log_errors
    def my_func(self):
        raise Exception()
    
    with pytest.raises(Exception):
        my_func(runner)
    
    error_log_count = 0
    for record in reversed(caplog.records):
        if '=== END ===' in record.message:
            break
        if record.levelno == logging.ERROR:
            error_log_count += 1
    assert error_log_count > 1

def test_run(runner: BaseRunner):
    assert runner.run() is None

@pytest.mark.parametrize(
    'print_begin,substring',
    [(True, 'BEGIN'), (False, None)],
)
def test_run_setup(runner: BaseRunner, print_begin, substring, caplog: pytest.LogCaptureFixture):
    runner.run_setup(print_begin=print_begin)
    if substring is None:
        assert caplog.text == ''
    else:
        assert substring in caplog.text

@pytest.mark.parametrize(
    'print_end,substring',
    [(True, 'END'), (False, None)],
)
def test_run_cleanup(runner: BaseRunner, print_end, substring, caplog: pytest.LogCaptureFixture):
    runner.run_cleanup(print_end=print_end)
    if substring is None:
        assert caplog.text == ''
    else:
        assert substring in caplog.text

@pytest.mark.parametrize(
    'template_str,resolve_paths,kwargs,expected',
    [
        ('no_replace', False, {}, 'no_replace'),
        ('[[NIPOPPY_DNAME_LOGS]]', False, {}, 'logs'),
        ('[[NIPOPPY_SOME_KWARG_PATH]]', False, {'some_kwarg_path': Path('a_path')}, 'a_path'),
        ('[[NIPOPPY_SOME_KWARG_PATH]]', True, {'some_kwarg_path': Path('a_path')}, str(Path('a_path').resolve())),
    ],
)
def test_process_template_str(runner: BaseRunner, template_str, resolve_paths, kwargs, expected):
    assert runner.process_template_str(template_str, resolve_paths, **kwargs) == expected

@pytest.mark.parametrize(
    'template_str,expected_relative_path',
    [
        ('[[NIPOPPY_DPATH_BIDS]]', 'bids'),
        ('[[NIPOPPY_DPATH_PYBIDS]]', Path('proc', 'pybids')),
    ],
)
def test_process_template_str_path(runner: BaseRunner, template_str, expected_relative_path):
    assert runner.process_template_str(template_str) == str(runner.global_configs.dataset_root / expected_relative_path)
    
def test_process_template_str_error_pattern(runner: BaseRunner):
    runner.template_replace_pattern = re.compile('\\[\\[NIPOPPY\\_(.*)\\_(.*)\\]\\]')
    with pytest.raises(ValueError, match='Expected exactly one match'):
        runner.process_template_str('[[NIPOPPY_SOME_KWARG]]')

def test_process_template_str_error_replace(runner: BaseRunner):
    with pytest.raises(RuntimeError, match='Unable to replace'):
        runner.process_template_str('[[NIPOPPY_INVALID]]')

@pytest.mark.parametrize(
    'tags,sep,substring',
    [
        (None, '-', 'runner'),
        ([3000], '-', '3000'),
        ([3000, 'BL'], '-', '3000-BL'),
        ([3000, 'BL'], '_', '3000_BL'),
    ],
)
def test_generate_fpath_log(runner: BaseRunner, tags, sep, substring):
    runner.sep = sep
    fpath = runner.generate_fpath_log(tags)
    assert runner.global_configs.dpath_scratch in fpath.parents
    assert runner.dname_logs in fpath.parts
    assert substring in str(fpath)

@pytest.mark.parametrize(
    'command_or_args,shell,capture_output,expected',
    [
        ('echo x', False, False, 'echo x'),
        (['echo', 'y'], False, False, 'echo y'),
        ('echo x', False, True, ('x\n', '')),
        (['echo', 'y'], False, True, ('y\n', '')),
        ('echo x && echo y 1>&2', True, True, ('x\n', 'y\n')),
        (['echo x && echo y 1>&2'], True, True, ('x\n', 'y\n')),
    ],
)
@pytest.mark.parametrize('check', [True, False])
def test_run_command(runner: BaseRunner, command_or_args, check, shell, capture_output, expected):
    
    if capture_output:
        runner.dry_run = False
    
    assert expected == runner.run_command(command_or_args, check=check, shell=shell, capture_output=capture_output)

@pytest.mark.parametrize('prefix_run', ['[RUN]', '<run>'])
@pytest.mark.parametrize('prefix_run_stdout', ['[RUN STDOUT]', '<run stdout>'])
@pytest.mark.parametrize('prefix_run_stderr', ['[RUN STDERR]', '<run stderr>'])
def test_run_command_log(runner: BaseRunner, prefix_run, prefix_run_stdout, prefix_run_stderr, caplog: pytest.LogCaptureFixture):
    runner.dry_run = False
    runner.log_prefix_run = prefix_run
    runner.log_prefix_run_stdout = prefix_run_stdout
    runner.log_prefix_run_stderr = prefix_run_stderr
    runner.run_command('echo x && echo y 1>&2', shell=True, capture_output=True)
    debug_log_count = 0
    stdout_log_count = 0
    stderr_log_count = 0
    for record in reversed(caplog.records):
        if record.levelno == logging.DEBUG:
            debug_log_count += 1
            if record.message.startswith(prefix_run_stdout):
                stdout_log_count += 1
            elif record.message.startswith(prefix_run_stderr):
                stderr_log_count += 1
        elif record.levelno == logging.INFO:
            assert record.message.startswith(prefix_run)
            break
    assert debug_log_count > 0
    assert stdout_log_count == 1
    assert stderr_log_count == 1

def test_run_command_error(runner: BaseRunner):
    runner.dry_run = False
    with pytest.raises(subprocess.CalledProcessError, match='non-zero exit status'):
        runner.run_command('ls invalid_path', check=True)
    assert runner.command_failed

@pytest.mark.parametrize('command', ['echo x', 'echo y'])
@pytest.mark.parametrize('prefix_run', ['[RUN]', '<run>'])
def test_log_command(runner: BaseRunner, command, prefix_run, caplog: pytest.LogCaptureFixture):
    runner.log_prefix_run = prefix_run
    runner.log_command(command)
    record = caplog.records[-1]
    assert record.levelno == logging.INFO
    assert record.message.startswith(prefix_run)
    assert command in record.message

@pytest.mark.parametrize('message', ['test', 'log'])
@pytest.mark.parametrize('level', [logging.DEBUG, logging.INFO, logging.WARNING, logging.ERROR, logging.CRITICAL])
def test_log(runner: BaseRunner, message, level, caplog: pytest.LogCaptureFixture):
    runner._log(message, level=level)
    record = caplog.records[-1]
    assert record.levelno == level
    assert record.message == message

@pytest.mark.parametrize('level', ['debug', 'info', 'warning', 'error', 'critical'])
def test_log_levels(runner: BaseRunner, level: str, caplog: pytest.LogCaptureFixture):
    getattr(runner, level)('message')
    record = caplog.records[-1]
    assert record.levelname == level.upper()
