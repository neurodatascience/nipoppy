from pathlib import Path

import pytest
from fids.fids import create_fake_bids_dataset
from nipoppy.workflow.runner import ProcpipeRunner

# import json
# from .conftest import global_configs_for_testing

# @pytest.fixture()
# def global_configs_dict(tmp_path: Path):
#     global_configs = global_configs_for_testing(tmp_path)
    
#     # dpath_container = tmp_path / 'containers'
#     # dpath_container.mkdir(exist_ok=True)
#     # for fname_fake_container in ['fmriprep_20.2.7.sif', 'fmriprep_23.1.3.sif', 'mriqc_23.1.0.sif']:
#     #     (dpath_container / fname_fake_container).touch()
#     # global_configs['CONTAINER_STORE'] = dpath_container
    
#     dpath_invocations = tmp_path / 'invocations'
#     dpath_invocations.mkdir(exist_ok=True)
#     for fname_fake_invocation in ['fmriprep-20.2.7.json', 'fmriprep-23.1.3.json', 'mriqc-23.1.0.json']:
#         fpath_fake_invocation = dpath_invocations / fname_fake_invocation
#         with fpath_fake_invocation.open('w') as file_invocation:
#             json.dump({}, file_invocation)
    
#     global_configs['PROC_PIPELINES'] = {
#         "fmriprep": {
#             "VERSION": ["20.2.7", "23.1.3"],
#             "CONTAINER": "fmriprep_{}.sif",
#             "INVOCATION_TEMPLATE": str(dpath_invocations / "fmriprep-{}.json")
#         },
#         "mriqc": {
#             "VERSION": "23.1.0",
#             "CONTAINER": "mriqc_{}.sif",
#             "INVOCATION_TEMPLATE": str(dpath_invocations / "mriqc-{}.json")
#         },
#     }
#     return global_configs

@pytest.fixture(
    scope='function',
    params=[
        ('patient1', 'baseline'),
        ('control1', 'followup'),
    ],
)
def runner(global_configs_fixture, tmp_path: Path, request: pytest.FixtureRequest) -> ProcpipeRunner:
    subject, session = request.param
    runner = ProcpipeRunner(
        global_configs_fixture, 
        'mriqc',
        subject,
        session,
    )
    runner.fpath_log = tmp_path / 'runner.log'
    return runner

def test_generate_fpath_log(runner: ProcpipeRunner):
    assert isinstance(runner.generate_fpath_log(), Path)

def test_run_setup(runner: ProcpipeRunner):
    assert runner.run_setup() is None

def test_setup_bids_db_exists(runner: ProcpipeRunner):
    assert runner.setup_bids_db() is None
    assert (runner.dpath_bids_db / 'layout_index.sqlite').exists()

@pytest.mark.parametrize(
    "subjects,sessions,datatypes,ignore_patterns,n_files_expected",
    [
        (['patient1', 'control1'], ['baseline', 'followup'], ['anat'], [], 2),
        (['patient1', 'control1'], ['baseline', 'followup'], ['anat', 'func'], [], 6),
        (['patient1', 'control1'], ['baseline', 'followup'], ['anat', 'func'], ['.*/anat/'], 4),
        (['patient1', 'control1'], ['baseline', 'followup'], ['anat', 'func'], ['.*/func/'], 2),
        (['patient1', 'control1'], ['baseline', 'followup'], ['anat', 'func'], ['.*/anat/', '.*/func/'], 0),
        (['other'], ['baseline'], ['anat'], [], 0),
    ],
)
def test_setup_bids_db_ignore(runner: ProcpipeRunner, subjects, sessions, datatypes, ignore_patterns, n_files_expected):
    create_fake_bids_dataset(
        output_dir=runner.global_configs.dpath_bids,
        subjects=subjects,
        sessions=sessions,
        datatypes=datatypes,
    )
    runner.fpath_pybids_ignore.parent.mkdir(parents=True, exist_ok=True)
    with open(runner.fpath_pybids_ignore, 'w') as file_ignore:
        for ignore_pattern in ignore_patterns:
            file_ignore.write(f'{ignore_pattern}\n')
    runner.setup_bids_db()
    assert len(runner.layout.get()) == n_files_expected

def test_setup_bids_db_no_ignore(runner: ProcpipeRunner, caplog: pytest.LogCaptureFixture):
    runner.setup_bids_db()
    assert any([
        (
            record.levelname == 'WARNING' and
            'No BIDS ignore file found at' in record.message
        )
        for record in caplog.records
    ])

def test_setup_bids_db_exists(runner: ProcpipeRunner, caplog: pytest.LogCaptureFixture):
    runner.setup_bids_db()
    caplog.clear()
    runner.setup_bids_db()
    assert any([
        (
            record.levelname == 'WARNING' and
            'Overwriting existing BIDS database directory' in record.message
        )
        for record in caplog.records
    ])

def test_setup_bids_db_empty(runner: ProcpipeRunner, caplog: pytest.LogCaptureFixture):
    runner.fpath_pybids_ignore.parent.mkdir(parents=True, exist_ok=True)
    with open(runner.fpath_pybids_ignore, 'w') as file_ignore:
        file_ignore.write('.*') # ignore everything
    runner.setup_bids_db()
    assert any([
        (
            record.levelname == 'WARNING' and
            'BIDS database is empty' in record.message
        )
        for record in caplog.records
    ])

def test_setup_input_directory(runner: ProcpipeRunner):
    dpath_input = runner.global_configs.dpath_bids
    assert runner.setup_input_directory() is None
    assert f'{dpath_input}:{dpath_input}:ro' in runner.singularity_flags

@pytest.mark.parametrize('with_work_dir', [True, False])
@pytest.mark.parametrize('with_bids_db', [True, False])
def test_setup_output_directories(runner: ProcpipeRunner, with_work_dir, with_bids_db):
    runner.with_work_dir = with_work_dir
    runner.with_bids_db = with_bids_db

    assert runner.setup_output_directories() is None
    assert f'{runner.dpath_output}:{runner.dpath_output}:rw' in runner.singularity_flags
    assert runner.dpath_output.exists()

    if with_work_dir:
        assert f'{runner.dpath_work}:{runner.dpath_work}:rw' in runner.singularity_flags
        assert runner.dpath_work.exists()

    if with_bids_db:
        assert f'{runner.dpath_bids_db}:{runner.dpath_bids_db}:rw' in runner.singularity_flags
        assert runner.dpath_bids_db.exists()

def test_check_paths_to_tar(tmp_path: Path, global_configs_fixture):
    runner = ProcpipeRunner(
        global_configs_fixture, 
        'fmriprep', # specifies paths to tar in Boutiques descriptor
        'patient1',
        'baseline',
    )
    runner.fpath_log = tmp_path / 'runner.log'
    runner.dpath_output_freesurfer = 'fake_freesurfer_dir' # needed for fmriprep
    assert len(runner.paths_to_tar) == 0
    assert runner.check_paths_to_tar() is None
    assert len(runner.paths_to_tar) > 0
    assert all([isinstance(path, Path) for path in runner.paths_to_tar])

def test_check_paths_to_tar_empty(runner: ProcpipeRunner):
    assert len(runner.paths_to_tar) == 0
    with pytest.raises(ValueError, match='No path to tar specified'):
        runner.check_paths_to_tar()

@pytest.mark.parametrize('with_work_dir', [True, False])
@pytest.mark.parametrize('with_bids_db', [True, False])
def test_run_cleanup(runner: ProcpipeRunner, with_work_dir, with_bids_db):
    runner.with_work_dir = with_work_dir
    runner.with_bids_db = with_bids_db
    runner.tar_outputs = False  # tarring is tested elsewhere
    runner.run_setup()
    runner.command_failed = False
    assert runner.run_cleanup() is None
    assert not runner.dpath_work.exists()
    assert not runner.dpath_bids_db.exists()

def test_run_cleanup_command_failed(runner: ProcpipeRunner):
    runner.with_work_dir = True
    runner.tar_outputs = False
    runner.run_setup()
    runner.command_failed = True
    assert runner.run_cleanup() is None
    assert runner.dpath_work.exists()
    assert not any([
        command.startswith('tar')
        for command in runner.command_history
        if isinstance(command, str)
    ])

def test_run_cleanup_tar(runner: ProcpipeRunner):
    runner.tar_outputs = True
    runner.command_failed = False
    runner.dpath_output.mkdir(parents=True, exist_ok=True)
    runner.paths_to_tar = [runner.dpath_output]
    assert runner.run_cleanup() is None
    [print(command) for command in runner.command_history]
    assert any([
        'tar' == command[0]
        for command in runner.command_history
    ])
    assert any([
        ['rm', '-rf', str(runner.dpath_output)] == command
        for command in runner.command_history
    ])

@pytest.mark.parametrize(
    'relative_paths_to_tar,zip_tar,ext',
    [
        (['my_path'], False, '.tar'),
        (['my_path', 'another_path'], False, '.tar'),
        (['my_path', 'another_path'], True, '.tar.gz'),
    ],
)
def test_tar_output_files(runner: ProcpipeRunner, tmp_path: Path, relative_paths_to_tar, zip_tar, ext):
    paths_to_tar = []
    for relative_path_to_tar in relative_paths_to_tar:
        path_to_tar: Path = tmp_path / relative_path_to_tar
        path_to_tar.mkdir(parents=True, exist_ok=True)
        paths_to_tar.append(path_to_tar)
    runner.tar_outputs = True
    runner.zip_tar = zip_tar
    runner.paths_to_tar = paths_to_tar
    assert runner.tar_output_files() is None
    assert all([
        Path(path).with_suffix(ext).exists()
        for path in paths_to_tar
    ])
    assert all([
        not Path(path).exists()
        for path in paths_to_tar
    ])

def test_tar_output_files_error(runner: ProcpipeRunner):
    runner.tar_outputs = True
    runner.paths_to_tar = ['fake_path']
    with pytest.raises(FileNotFoundError):
        runner.tar_output_files()

@pytest.mark.parametrize(
    'pipeline_name,pipeline_version',
    [
        ('fmriprep', '20.2.7'),
        ('mriqc', '23.1.0'),
    ],
)
def test_path_attributes(runner: ProcpipeRunner, pipeline_name, pipeline_version):
    runner.pipeline_name = pipeline_name
    runner.pipeline_version = pipeline_version
    dataset_root = runner.global_configs.dataset_root
    assert runner.fpath_pybids_ignore == dataset_root / 'proc' / 'pybids' / 'ignore_patterns' / f'{pipeline_name}-{pipeline_version}.txt'
    assert runner.dpath_pipeline_derivatives == dataset_root / 'derivatives' / pipeline_name / pipeline_version
    assert runner.dpath_output == dataset_root / 'derivatives' / pipeline_name / pipeline_version / 'output'
    assert runner.dpath_work == dataset_root / 'derivatives' / pipeline_name / pipeline_version / 'work' / f'{runner.subject}-{runner.session}'
    assert runner.dpath_bids_db == dataset_root / 'proc' / 'pybids' / 'bids_db' / f'{pipeline_name}-{pipeline_version}-{runner.subject}-{runner.session}'
