# Creating the manifest file

```{toctree}
---
hidden:
includehidden:
---
Example script 1<example1>
Example script 2<example2>
Example script 3<example3>
```

This guide shows how to create a study's [manifest file](<project:../../explanations/manifest.md>), which is a list of participants recruited in the study, their visits, and expected data modalities.

:::{note}
If the Nipoppy study was initialized from an existing BIDS dataset with `nipoppy init --bids-source`, then a manifest file containing valid and accurate entries for the imaging data was automatically generated from the BIDS input. In this case, it is not necessary to manually insert or update the imaging data information in the manifest file.

However, if the study has additional visits that were not present in the BIDS data (e.g., non-imaging visits), they will need to be added to the manifest separately.
:::

Every Nipoppy study should have a manifest file at {{fpath_manifest}}.
This file is tab-separated and has four columns: `participant_id`, `visit_id`, `session_id` and `datatype`.
Here is an example of a valid manifest file:
:::{csv-table}
---
file: ../../../../nipoppy/data/examples/sample_manifest.tsv
header-rows: 1
delim: tab
---
:::

::::{admonition} Raw content of the example manifest file
---
class: dropdown
---
:::{literalinclude} ../../../../nipoppy/data/examples/sample_manifest.tsv
---
linenos: True
---
:::
::::

## Columns in the manifest file

:::{attention}
There must be only **one row** per unique `participant_id`/`visit_id` combination.
:::

### `participant_id`

A unique identifier for a participant in the study. Must be present in every row.
- **Cannot** contain non-alphanumeric characters (spaces, dashes, underscores, etc.)
- **Cannot** have the `sub-` prefix
- Example valid values: `001`, `ABC01`
    - Example valid but not recommended: `control1`, `alzheimers1`, `sub1`
- Example invalid values: `sub-001`, `ABC.01`

::::{admonition} What if the participant IDs in my existing study files are not Nipoppy-compatible?
---
class: dropdown
---
In those situations, you should still make sure that `participant_id` values in the Nipoppy manifest do not contain non-alphanumeric characters.
To keep track of the mapping between the Nipoppy `participant_id`s and the original study's IDs (also referred to as "recruitment IDs"), you should create a [recruitment.tsv](../../explanations/recruitment.md) file.

Note that existing/original study files *do not* have to be manually updated to use the Nipoppy `participant_id`s. The same goes for file/directory names in the imaging source data (e.g. DICOM directories) -- it is possible to configure the behaviour of some Nipoppy operations to account for the presence of `recruitment_id`s instead of `participant_id`s in file/directory names.
::::

### `visit_id`

An identifier for a data collection event (imaging or non-imaging). Must be present in every row.

### `session_id`

An identifier for an imaging data collection event. Should be left empty if no imaging data was collected.
- **Cannot** contain non-alphanumeric characters (spaces, dashes, underscores, etc.)
- **Cannot** have the `ses-` prefix
- Example valid values: `1`, `baseline`, `Month12`
- Example invalid values: `ses-1`, `follow-up` `Month_12`

:::{admonition} Session IDs vs visit IDs
:class: note
Nipoppy uses the term "session ID" for imaging data, following the convention established by BIDS.
The term "visit ID", on the other hand, is used to refer to any data collection event (not necessarily imaging-related), and is more common in clinical contexts.

**In most cases, `session_id` and `visit_id` will be identical (or `session_id`s will be a subset of `visit_id`s).**
However, having two descriptors becomes particularly useful when imaging and non-imaging assessments do not use the same naming conventions.
:::

### `datatype`

A list of datatypes expected to be in the {term}`BIDS` data. Should be left empty if no imaging data was collected.
- Example valid values: `['anat']`, `['anat', 'dwi']`

Common {term}`MRI` datatypes include:
- `anat`: anatomical MRI
- `dwi`: diffusion MRI
- `func`: functional MRI
- `fmap`: field maps

The full list of valid datatypes is listed in the [BIDS schema](https://github.com/bids-standard/bids-specification/blob/master/src/schema/objects/datatypes.yaml).

:::{note}
If it is too difficult to determine the exact imaging datatypes collected for a given participant and session, you can set the `datatype` value for this row to be all available datatypes in the study.
:::

## Guidelines and examples for creating a study's manifest file

We **highly recommend** writing a script that automatically generates the manifest based on existing files.
These can be tabular files (CSVs, TSVs, Excel sheets, etc.) in {{dpath_src_tabular}} and/or imaging data in {{dpath_src_imaging}}.
The script can be rerun whenever the source files are modified to automatically update the manifest, reducing future manual work and keeping a record of what was done.

Below are some examples from common cases we have encountered.
Note that the example use Python scripts, but other programming languages like R can also be used to generate the manifest.

::::{grid} 1 2 3 3
:::{grid-item-card} [Example 1](./example1)
Creating a manifest from another tabular file for a cross-sectional study with different imaging datatypes
:::
:::{grid-item-card} [Example 2](./example2)
Creating a manifest from wide-form tabular files for a longitudinal study with imaging and non-imaging visits
:::
:::{grid-item-card}  [Example 3](./example3)
Creating a manifest from data directories on disk for a study with different imaging datatypes
:::
::::
