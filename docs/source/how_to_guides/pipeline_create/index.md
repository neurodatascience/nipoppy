# Adding a pipeline to Nipoppy

This guide explains how to generate and customize a pipeline configuration for use with Nipoppy.

## Create a Boutiques descriptor file

Nipoppy pipeline execution relies on [Boutiques](https://boutiques.github.io/).
We recommend creating (or finding) a descriptor for the desired pipeline as the first step for adding a new pipeline to Nipoppy.

A Boutiques descriptor is a JSON file that describes:

- the command-line interface of your tool (`"command-line"`),
- required inputs and their types (`"inputs"`),
- outputs and how to find them (`"output-files"`),
- and execution environment (e.g., Docker/Singularity container via `"container-image"`).

Example: descriptor for [FSL SIENA](https://fsl.fmrib.ox.ac.uk/fsl/docs/structural/siena/index.html)

<div style="max-height: 400px; overflow-y: auto; border: 1px solid #ccc; padding: 1em;">

```{literalinclude} data/descriptor.json
---
linenos: True
language: json
---
```

</div>


````{admonition} Helpful commands
---

class: dropdown
---
`bosh` is the CLI from Boutiques. It comes packaged with Nipoppy.

Searching for a descriptor:

```console
$ bosh search
```

Validating a descriptor:

```console
$ bosh validate descriptor.json
```

Generating an invocation template:

```console
$ bosh example descriptor.json > invocation.json
```

Simulating a run:

```console
$ bosh exec simulate descriptor.json invocation.json
```

````

### References

- Full schema: <https://github.com/boutiques/boutiques/blob/master/boutiques/schema/descriptor.schema.json/>
- Documentation: <https://boutiques.github.io/doc/>

## Create the remaining configuration files

Use the `nipoppy pipeline create` command to generate a sample configuration. Nipoppy supports three pipeline types: `bidsification`, `processing`, and `extraction`.

```console
nipoppy pipeline create \
    --type processing \
    --source-descriptor <EXISTING_DESCRIPTOR_FILE> \
    <OUTPUT_PIPELINE_DIR>
```

:::{note}
It is also possible to run this command without the `--source-descriptor` option, but that will require more downstream manual editing since the files will not be pre-populated with information from the descriptor.
:::

This will create the following structure:

```console
$ tree ./pipelines/howto
pipelines/howto
├── config.json
├── descriptor.json
├── hpc.json
├── invocation.json
└── tracker.json
```

## Edit the configuration files

:::{attention}
Nipoppy uses string substitutions to inject study-specific information (e.g., paths, participant IDs) into configuration files at runtime.
See [this page](<project:../../reference/substitutions.md>) for lists of available substitutions for each type of configuration file.
:::

### File common for all pipeline types

#### `config.json`

Edit general pipeline metadata and settings.
See the schemas for {ref}`BIDSification <bidsification-pipeline-config-schema>`, {ref}`processing <processing-pipeline-config-schema>` and {ref}`extraction <extraction-pipeline-config-schema>` pipelines.

##### Key fields

- **`"NAME"`** and **`"VERSION"`** (if no source descriptor was used)
- **`"CONTAINER_CONFIG"`** -> **`"BIND_PATHS"`**: paths to volumes to be mounted to the container (format: `local_path[:path_inside_container[:mode]]`)
- **`"STEPS"`** -> **`"ANALYSIS_LEVEL"`**: to control the looping (if any) performed by Nipoppy
    - `"participant_session"`: iterate over all participant-session pairs (default)
    - `"participant`": iterate over participants only
    - `"session`": iterate over sessions only
    - `"group`": single iteration, for pipelines that do group analysis or handle all looping internally
- **`"GENERATE_PYBIDS_DATABASE`"**: only set to `true` if the pipeline accepts a [PyBIDS](https://bids-standard.github.io/pybids/) database path as input. Nipoppy will then index the raw BIDS data and create a database that is constrained to the participant and/or session being run. The `[[NIPOPPY_DPATH_PIPELINE_BIDS_DB]]` substitution can be used to inject the path to this database into the invocation file.
    - Indexing can further be controlled by the user via the **`"PYBIDS_IGNORE_FILE`"** field
- **`"VARIABLES`"**: for pipelines that require information (typically file/directory paths) for which there is no good default (e.g. path to a configuration file or a FreeSurfer license file). This should be a dictionary with variable names as keys and descriptions as values, e.g., `{"REQUIRED_FILE": "This file is for running the pipeline"}`

##### Example for the [FSL SIENA](https://fsl.fmrib.ox.ac.uk/fsl/docs/structural/siena/index.html) pipeline

```{literalinclude} data/config.json
---
linenos: True
language: json
emphasize-lines: 2-3,10,17,20,24
---
```

:::{note}
`[[NIPOPPY_DPATH_CONTAINERS]]`: will be replaced dynamically based on the Nipoppy layout.

`[[PIPELINE_NAME]]` and `[[PIPELINE_VERSION]]` are replaced dynamically during execution using the value from the `"NAME"` and `"VERSION"` fields,
respectively.
:::

#### `descriptor.json`

Refer to [Creating a Boutiques descriptor](#create-a-boutiques-descriptor-file) above if you did not use a source descriptor.

#### `invocation.json`

Defines default input arguments to the pipeline.
The keys in the invocation file should match the `"id"` field of input items in the descriptor.
At pipeline runtime, the descriptor and invocation files will be used to generate the command to be executed.

```{literalinclude} data/invocation.json
---
linenos: True
language: json
---
```

:::{note}
You can automatically generate an example `invocation.json` file with all the required keys from the descriptor.

```bash
bosh example ./pipelines/howto/descriptor.json > ./pipelines/howto/invocation.json
```

:::

#### `hpc.json` (Optional)

Defines HPC job submission parameters.
See {doc}`../parallelization/hpc_scheduler` for more information on configuring HPC schedulers with Nipoppy.

```json
{
    "ACCOUNT": "[[HPC_ACCOUNT_NAME]]",
    "TIME": "1:00:00",
    "CORES": "1",
    "MEMORY": "16G",
    "ARRAY_CONCURRENCY_LIMIT": ""
}
```

### Files specific to processing pipelines

#### `tracker.json`

Defines output tracking paths.
See [here](#how-to-track-processing) for more information about pipeline tracking.

```json
{
    "PATHS": [
        "[[NIPOPPY_BIDS_PARTICIPANT_ID]]/[[NIPOPPY_BIDS_SESSION_ID]]/anat/[[NIPOPPY_BIDS_PARTICIPANT_ID]]_[[NIPOPPY_BIDS_SESSION_ID]]*_example.txt"
    ],
    "PARTICIPANT_SESSION_DIR": "[[NIPOPPY_BIDS_PARTICIPANT_ID]]/[[NIPOPPY_BIDS_SESSION_ID]]"
}
```

:::{note}
Tracking is always done at the participant-session level, no matter the value of `"ANALYSIS_LEVEL"` in `config.json`.

The tracked paths are expected to be relative to {{dpath_pipeline_output}}.

Assuming a participant ID `001` and session ID `A`, the template strings will resolve to:

- `[[NIPOPPY_PARTICIPANT_ID]]`: `001`
- `[[NIPOPPY_BIDS_PARTICIPANT_ID]]`: `sub-001`
- `[[NIPOPPY_SESSION_ID]]`: `A`
- `[[NIPOPPY_BIDS_SESSION_ID]]`: `ses-A`
:::

## Upload to the Nipoppy pipeline store (optional)

Nipoppy provides an easy way to upload and install [community-developed pipelines](https://zenodo.org/search?q=metadata.subjects.subject%3A%22Nipoppy%22&l=list&p=1&s=10&sort=bestmatch) via Zenodo.

:::{important}
Before uploading a pipeline to the catalog via the Nipoppy CLI, you must [generate a Zenodo token](https://zenodo.org/account/settings/applications/tokens/new/).
:::

```console
nipoppy pipeline upload \
  --password-file <PASSWORD_FILE> \
  <PIPELINE_DIR>
```

:::{note}
To update an existing Zenodo record, use the `--zenodo-id` flag.
:::

### `zenodo.json` (Optional)

By default, Nipoppy infers the value using the metadata from the user's Zenodo account.

To provide custom metadata for your Zenodo record, you must specify it in the optional `zenodo.json` file.
This file is not part of the `config.json` file.

```{literalinclude} /../../nipoppy/data/template_pipeline/zenodo.json
---
linenos: True
language: json
---
```
