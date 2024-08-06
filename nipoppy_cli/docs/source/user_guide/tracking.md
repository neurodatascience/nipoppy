# Tracking pipeline processing status

Nipoppy trackers search for expected file paths or patterns in pipeline output files. They are specific to pipelines and versions, and can be configured to include custom paths for various levels of granularity.

## Summary

### Prerequisites

- A Nipoppy dataset with a valid global configuration file and an accurate manifest
    - See the [Quickstart guide](../quickstart.md) for instructions on how to set up a new dataset
- Processed imaging data the {{dpath_derivatives}} directory
    - See <project:processing.md> for expected subdirectory structure

### Data directories and files

| Directory or file | Content description |
|---|---|
| {{dpath_derivatives}} | **Input** -- {{content_dpath_derivatives}} |
| {{fpath_imaging_bagel}} | **Output** -- Tabular file containing processing status for each participant/session and pipeline |

### Commands

- Command-line interface: [`nipoppy track`](<project:../cli_reference/track.md>)
- Python API: {class}`nipoppy.workflows.PipelineTracker`

### Workflow

1. Nipoppy will loop over all participants/sessions that have BIDS data according to the {term}`doughnut file`
2. For each participant-session pair:
    1. Paths in the pipeline's tracker configuration will be processed such that template strings related to the participant/session are replaced by the appropriate values
    2. Each path in the list is checked, then a status is assigned, and the bagel file is updated accordingly

## Configuring a pipeline tracker

The global configuration file should include paths to tracker configuration files, which are {term}`JSON` files containing lists of dictionaries.

Here is example of tracker configuration file (default for MRIQC 23.1.0):
```{literalinclude} ../../../nipoppy/data/examples/sample_tracker_configs/mriqc-23.1.0.json
```

Importantly, pipeline completion status is **not** inferred from exit codes as trackers are run independently of the pipeline runners. Moreover, the default tracker configuration files are somewhat minimal and do not check all possible output files generated these pipelines.

```{tip}
- The paths are expected to be relative to the {{dpath_derivatives}}`/<PIPELINE_NAME>/<PIPELINE_VERSION>/output` directory.
- "Glob" expressions (i.e., that include `*`) are allowed in paths. If at least one file matches the expression, then the file will be considered found for that expression.
```

```{note}
The template strings `[[NIPOPPY_<ATTRIBUTE_NAME>]]` work the same way as the ones in the [global configuration file](<global-config-template-strings>) and the [pipeline invocation files](<invocation-template-strings>) -- they are replaced at runtime by appropriate values.
```

```{attention}
Currently, only the tracker configuration with `pipeline_complete` in the `NAME` field will be used, but we are planning to extend trackers to allow multiple statuses per pipeline. Stay tuned!
```

Given a dataset with the following content in {{dpath_derivatives}}:
```{literalinclude} ./inserts/mriqc_outputs.txt
---
class: no-copybutton
---
```

Running the tracker with the above configuration will result in the imaging bagel file showing:
```{csv-table}
---
file: ./inserts/mriqc_bagel.csv
header-rows: 1
---
```

```{note}
If there is an existing bagel, the rows relevant to the specific pipeline, participants, and sessions will be updated. Other rows will be left as-is.
```

The `pipeline_complete` column can have the following values:
* `SUCCESS`: all specified paths have been found
* `FAIL`: at least one of the paths has not been found

## Running a pipeline tracker

### Using the command-line interface

To track all available participants and sessions, run:
```console
$ nipoppy track \
    --dataset-root <DATASET_ROOT> \
    --pipeline <PIPELINE_NAME>
```
where `<PIPELINE_NAME>` correspond to the pipeline name as specified in the global configuration file.

```{note}
If there are multiple versions for the same pipeline in the global configuration file, use `--pipeline-version` to specify the desired version. By default, the first version listed for the pipeline will be used.
```

The tracker can also be run on a single participant and/or session at a time:
```console
$ nipoppy track \
    --dataset-root <DATASET_ROOT> \
    --pipeline <PIPELINE_NAME> \
    --participant-id <PARTICIPANT_ID> \
    --session-id <SESSION_ID>
```

See the [CLI reference page](<project:../cli_reference/track.md>) for more information on additional optional arguments.

```{note}
Log files for this command will be written to {{dpath_logs}}`/track`
```

### Using the Python API

```python
from nipoppy.workflows import PipelineTracker

# replace by appropriate values
dpath_root = "<DATASET_ROOT>"
pipeline_name = "<PIPELINE_NAME>"

workflow = PipelineTracker(
    dpath_root=dpath_root,
    pipeline_name=pipeline_name,
)
workflow.run()
```

See the API reference for {class}`nipoppy.workflows.PipelineTracker` for more information on optional arguments (they correspond to the ones for the [CLI](<project:../cli_reference/track.md>)).

## Next steps

If some participants/sessions have failed processing or have not been run yet, they should be [run again](./processing.md).

Once the dataset has been processed with a pipeline, [Nipoppy extractors](./extraction.md) can be used to obtain analysis-ready imaging-derived phenotypes (IDPs).
