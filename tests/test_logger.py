import logging
from pathlib import Path

import pytest
from nipoppy.logger import create_logger

@pytest.mark.parametrize('fpath', [None, 'test.log'])
def test_create_logger(caplog: pytest.LogCaptureFixture, tmp_path: Path, fpath):
    if fpath is not None:
        fpath = tmp_path / fpath
    assert isinstance(create_logger('test', fpath), logging.Logger)
    if fpath is not None:
        assert str(fpath) in caplog.text
    else:
        assert 'will not write to a log file' in caplog.text

def test_create_logger_set_fpath(tmp_path: Path):
    fpath_log = tmp_path / 'test.log'
    if fpath_log.exists():
        fpath_log.unlink()
    assert isinstance(create_logger('test', fpath_log), logging.Logger)
    assert fpath_log.exists()
