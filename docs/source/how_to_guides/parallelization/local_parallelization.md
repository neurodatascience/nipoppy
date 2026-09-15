# Parallelizing pipeline runs on non-HPC systems

This guide shows possible ways to parallelize pipeline runs on computer systems without job schedulers supported by Nipoppy.

## Getting a list of participants and sessions to run

The [`nipoppy bidsify`](<project:../../reference/cli_reference/bidsify.rst>), [`nipoppy process`](<project:../../reference/cli_reference/process.rst>), and [`nipoppy extract`](<project:../../reference/cli_reference/extract.rst>) commands all have a `--write-list` option.
If this option is specified, instead of launching the pipeline, the command will write a TSV file of participant and session IDs that need to be run.

```console
$ nipoppy <SUBCOMMAND> \
    --dataset <NIPOPPY_STUDY_ROOT> \
    --pipeline <PIPELINE_NAME> \
    --write-list <PATH_TO_TSV_FILE>
```

## Launching parallel processes

The TSV file created with the `--write-list` option can be used to launch parallel runs.
On Linux systems, this can be done using the [`parallel`](https://www.gnu.org/software/parallel/) tool if it is installed:

```console
$ parallel \
    --colsep '\t' \
    --jobs <N_MAX_JOBS> \
    nipoppy <SUBCOMMAND> \
        --dataset <NIPOPPY_STUDY_ROOT> \
        --pipeline <PIPELINE_NAME> \
        # other desired options \
        # ... \
        --participant-id {1} \
        --session-id {2} \
    :::: <PATH_TO_TSV_FILE>
```

If `parallel` or other similar utilities are not available, custom scripts would be needed to launch the runs in parallel.
