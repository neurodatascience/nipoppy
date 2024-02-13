from nipoppy.workflow.runner import ProcpipeRunner

class MriqcRunner(ProcpipeRunner):

    def __init__(self, global_configs, subject, session, pipeline_version: str | None = None, with_work_dir=True, with_bids_db=True, **kwargs) -> None:
        super().__init__(
            global_configs=global_configs, 
            pipeline_name='mriqc',
            with_templateflow=True,
            subject=subject,
            session=session,
            pipeline_version=pipeline_version,
            with_work_dir=with_work_dir,
            with_bids_db=with_bids_db,
            **kwargs,
        )
