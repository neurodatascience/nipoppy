# Running processing pipelines

Just like with the BIDS conversion pipelines, Nipoppy uses the {term}`Boutiques framework <Boutiques>` to run image processing pipelines. By default, new Nipoppy datasets (as created with [`nipoppy init`](<project:../cli_reference/init.md>)) are populated with descriptor files and default invocation files for the following processing pipelines:
- [fMRIPrep](https://fmriprep.org/en/stable/), a pipeline for preprocessing anatomical and functional MRI data.
- [MRIQC](https://mriqc.readthedocs.io/en/latest/index.html), a pipeline for automated quality control (QC) metric extraction

```{note}
Although fMRIPrep and MRIQC are both [BIDS Apps](https://bids-apps.neuroimaging.io/about/), Nipoppy can also be used to run pipelines that are not BIDS Apps. Custom pipelines can be added by creating a Boutiques descriptor file and modifying the global configuration file accordingly.
```

## Summary

### Prerequisites

- A Nipoppy dataset with a valid global configuration file and an accurate manifest
    - See the [Quickstart guide](../quickstart.md) for instructions on how to set up a new dataset
- Raw imaging data organized according to the {term}`BIDS` standard in the {{dpath_bids}} directory
    - See <project:bids_conversion.md>

```{include} ./inserts/apptainer_stub.md
```

### Data directories

| Directory | Content description |
|---|---|
| {{dpath_bids}} | **Input** -- {{content_dpath_bids}} |
| {{dpath_derivatives}} | **Output** -- {{content_dpath_derivatives}} |

Within the {{dpath_derivatives}} directory, output files for a specific pipeline are organized like this:
```{literalinclude} ./inserts/pipeline_derivatives.txt
---
class: no-copybutton
---
```

### Commands

- Command-line interface: [`nipoppy run`](<project:../cli_reference/run.md>)
- Python API: {class}`nipoppy.workflows.PipelineRunner`

### Workflow

1. Nipoppy will loop over all participants/sessions that *have* BIDS data according to the {term}`doughnut file` but *have not* yet successfully completed the pipeline according the the imaging derivatives bagel file
    - An existing, out-of-date doughnut file can be updated with [`nipoppy doughnut --regenerate`](../cli_reference/doughnut.md)
2. For each participant-session pair:
    1. The pipeline's invocation will be processed such that template strings related to the participant/session and dataset paths are replaced by the appropriate values
    2. A [PyBIDS](https://bids-standard.github.io/pybids/) database indexing the BIDS data for this participant and session is created in a subdirectory inside {{dpath_bids_db}}
    3. The pipeline is launched using {term}`Boutiques`, which will be combine the processed invocation with the pipeline's descriptor file to produce and run a command-line expression

## Configuring processing pipelines

Just like with BIDS converters, pipeline and pipeline step configurations are set in the global configuration file (see [here](./global_config.md) for a more complete guide on the fields in this file).

There are several files in pipeline step configurations that can be further modified to customize pipeline runs:
- `INVOCATION_FILE`: a {term}`JSON` file containing key-value pairs specifying runtime parameters. The keys correspond to entries in the pipeline's descriptor file.
    - Invocation files are in the {{dpath_invocations}} directory, while descriptor files are in the {{dpath_descriptors}}
- `PYBIDS_IGNORE_FILE`: a {term}`JSON` file containing a list of file names or patterns to ignore when building the [PyBIDS](https://bids-standard.github.io/pybids/) database
    - These files should be in the {{dpath_bids_ignore_patterns}} directory

```{warning}
Pipeline step configurations also have a `DESCRIPTOR_FILE` field, which points to the {term}`Boutiques` descriptor of a pipeline. Although descriptor files can be modified, it is not needed and we recommend that less advanced users keep the default.
```

### Customizing pipeline invocations

```{include} ./inserts/boutiques_stub.md
```

(invocation-template-strings)=
{{template_strings_proc_runner}}

## Running a processing pipeline

### Using the command-line interface

To process all participants and sessions in a dataset (sequentially), run:
```console
$ nipoppy run \
    --dataset-root <DATASET_ROOT> \
    --pipeline <PIPELINE_NAME>
```
where `<PIPELINE_NAME>` correspond to the pipeline name as specified in the global configuration file.

```{note}
If there are multiple versions for the same pipeline in the global configuration file, use `--pipeline-version` to specify the desired version. By default, the first version listed for the pipeline will be used.

Similarly, if `--pipeline-step` is not specified, the first step defined in the global configuration file will be used.
```

The pipeline can also be run on a single participant and/or session (useful for batching on clusters and testing pipelines/configurations):
```console
$ nipoppy bidsify \
    --dataset-root <DATASET_ROOT> \
    --pipeline <PIPELINE_NAME> \
    --participant-id <PARTICIPANT_ID> \
    --session-id <SESSION_ID>
```

```{hint}
The `--simulate` argument will make Nipoppy print out the command to be executed with Boutiques (instead of actually executing it). It can be useful for checking runtime parameters or debugging the invocation file.
```

See the [CLI reference page](<project:../cli_reference/run.md>) for more information on additional optional arguments.

```{note}
Log files for this command will be written to {{dpath_logs}}`/run`
```

### Using the Python API

```python
from nipoppy.workflows import PipelineRunner

# replace by appropriate values
dpath_root = "<DATASET_ROOT>"
pipeline_name = "<PIPELINE_NAME>"

workflow = PipelineRunner(
    dpath_root=dpath_root,
    pipeline_name=pipeline_name,
)
workflow.run()
```

See the API reference for {class}`nipoppy.workflows.PipelineRunner` for more information on optional arguments (they correspond to the ones for the [CLI](<project:../cli_reference/run.md>)).

## Next steps

[Nipoppy trackers](./tracking.md) can be used to assess the status of processing pipelines being run on participants/sessions in a dataset.

Once the entire dataset has been processed with a pipeline, [Nipoppy extractors](./extraction.md) can be used to obtain analysis-ready imaging-derived phenotypes (IDPs).
