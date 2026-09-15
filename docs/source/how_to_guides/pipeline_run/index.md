# Running a pipeline

This guide shows how to run a pipeline with Nipoppy.

## Listing installed pipelines

The `nipoppy pipeline list` command displays pipelines that can be run for a given study. Here is an example command output:

```
INFO     Available bidsification pipelines and versions:
INFO             - bidscoin  (4.3.2)
INFO             - dcm2bids  (3.1.0, 3.2.0)
INFO             - heudiconv (0.12.2)
INFO     Available processing pipelines and versions:
INFO             - bids-validator (2.0.3)
INFO             - fmriprep       (20.2.7, 23.1.3, 24.1.1)
INFO             - freesurfer     (6.0.1, 7.3.2)
INFO             - mriqc          (23.1.0)
INFO             - qsiprep        (0.23.0)
INFO     Available extraction pipelines and versions:
INFO             - fs_stats  (0.2.1)
INFO             - static_FC (0.1.0)
```

If the pipeline you want to run is not listed, you will have to [install](<project:../pipeline_install/index.md>) it first.

## Running the pipeline

The command to run a pipeline depends on the **pipeline type**:
- BIDSification pipelines: [`nipoppy bidsify`](<project:../../reference/cli_reference/bidsify.rst>)
- Processing pipelines: [`nipoppy process`](<project:../../reference/cli_reference/process.rst>)
- Extraction pipelines: [`nipoppy extract`](<project:../../reference/cli_reference/extract.rst>)

The minimal command to run any of these commands is:

```console
$ nipoppy <SUBCOMMAND> \
    --dataset <NIPOPPY_STUDY_ROOT> \
    --pipeline <PIPELINE_NAME>
```

Where `<SUBCOMMAND>` is either `bidsify`, `process`, or `extract`.

If there are multiple versions for the same pipeline in the global configuration file, use `--pipeline-version` to specify the desired version. By default, the latest version out of the installed pipelines will be used.

Similarly, if `--pipeline-step` is not specified, the first step defined in the pipeline configuration file will be used.

The above command will run the pipeline on all participants and/or sessions who have not already completed the pipeline (according to the {term}`curation status <curation status file>` and {term}`processing status <processing status file>` files). It is also possible to restrict the run to a single participant and/or session, which can be useful for testing pipelines/configurations:

```console
$ nipoppy <SUBCOMMAND> \
    --dataset <NIPOPPY_STUDY_ROOT> \
    --pipeline <PIPELINE_NAME> \
    --participant-id <PARTICIPANT_ID> \
    --session-id <SESSION_ID>
```

### Testing a newly installed pipeline

We recommend always testing a new pipeline **in simulate mode** with a single participant and session and double-checking the generated command. This can be done with the `--simulate` flag. For example, to test the fMRIPrep 24.1.1 pipeline this way, run:

```console
$ nipoppy process \
    --dataset <NIPOPPY_STUDY_ROOT> \
    --pipeline fmriprep \
    --pipeline-version 24.1.1 \
    --participant-id <PARTICIPANT_ID> \
    --session-id <SESSION_ID> \
    --simulate
```

<!-- TODO link to HPC page once that exists -->
