import os
import re
from pathlib import Path

from boutiques import bosh

from nipoppy.workflow.utils import session_id_to_bids_session
from nipoppy.workflow.runner import ProcpipeRunner

class FmriprepRunner(ProcpipeRunner):

    re_freesurfer_version = re.compile('[\d+?]\.[\d+?]\.[\d+?]')
    freesurfer_name = 'freesurfer'
    freesurfer_license_descriptor_id = 'fs_license_file' # for boutiques query
    freesurfer_license_envvar = 'FS_LICENSE'

    def __init__(self, global_configs, subject, session, pipeline_version: str | None = None, **kwargs) -> None:
        super().__init__(global_configs, 'fmriprep', subject=subject, session=session, pipeline_version=pipeline_version, with_templateflow=True, **kwargs)
        self._freesurfer_version = None
        self._fpath_freesurfer_license = None

    def run_setup(self, **kwargs):
        output = super().run_setup(**kwargs)

        # freesurfer output directory and license file
        self.setup_freesurfer()

        return output

    def setup_freesurfer(self, check_license_path=True):

        # store freesurfer outputs in a separate directory from other
        # fmriprep outputs
        self.add_singularity_symmetric_bind_path(
            self.dpath_output_freesurfer,
        )

        # look for license path in invocation
        fpath_freesurfer_license = bosh([
            'evaluate',
            self.descriptor_template,
            self.invocation_template,
            f'inputs/id={self.freesurfer_license_descriptor_id}',
        ]).get(self.freesurfer_license_descriptor_id, None)

        if fpath_freesurfer_license is not None:
            fpath_freesurfer_license = self.process_template_str(
                fpath_freesurfer_license,
            )

        # check if environment variable for licence is set
        else:
            fpath_freesurfer_license = os.environ.get(
                self.freesurfer_license_envvar,
            )
            if fpath_freesurfer_license is not None:
                self.add_singularity_envvar(
                    self.freesurfer_license_envvar,
                    fpath_freesurfer_license,
                )

        if check_license_path:
            if fpath_freesurfer_license is None:
                raise RuntimeError(
                    'No Freesurfer license file specified in invocation file '
                    f'and environment variable {self.freesurfer_license_envvar}'
                    ' is not set'
                )
            elif not Path(fpath_freesurfer_license).exists():
                raise FileNotFoundError(
                    'Freesurfer license file does not exist'
                    f': {fpath_freesurfer_license}'
                )

        self.info(f'Found Freesurfer license file: {fpath_freesurfer_license}')

        self.add_singularity_symmetric_bind_path(
            fpath_freesurfer_license,
            mode='ro',
        )

    @property
    def freesurfer_version(self) -> str:
        if self._freesurfer_version is None:
            # run recon-all -version to get version string
            self.info(f'Checking FreeSurfer version from container for fMRIPrep version {self.pipeline_version}')
            version_str, _ = self.run_command(
                f'{self.global_configs.singularity_path} exec {self.fpath_container} recon-all -version',
                capture_output=True,
            )
            if not self.dry_run:
                match = self.re_freesurfer_version.search(version_str)
                if match is not None:
                    self._freesurfer_version = match.group()
                else:
                    raise RuntimeError(
                        'Could not extract Freesurfer version from container'
                        f' using regex pattern: {self.re_freesurfer_version.pattern}'
                    )
            else:
                self._freesurfer_version = '' # dummy version if dry run
        return self._freesurfer_version
    
    @property
    def dpath_output_freesurfer(self) -> Path:
        dpath_derivatives_freesurfer = self.global_configs.get_dpath_pipeline_derivatives(
            self.freesurfer_name,
            self.freesurfer_version,
            check_version=False, # freesurfer does not need to be in global configs
        )
        bids_session = session_id_to_bids_session(self.session)
        return dpath_derivatives_freesurfer / self.dname_output / bids_session

    def __str__(self) -> str:
        return self._str_helper([
            self.pipeline_version,
            self.subject, self.session,
        ])
