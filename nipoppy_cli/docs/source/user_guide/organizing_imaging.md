# Organizing raw imaging data

To use Nipoppy to convert imaging data to the {term}`BIDS` standard, the data first needs to be organized in a way that Nipoppy can understand and pass to underlying BIDS converters (see <project:bids_conversion.md>). Since different studies typically follow their own methods for raw imaging data organization, this step may require the creation of a custom mapping file or the overriding of some existing methods in the Python API.

## Summary

### Prerequisites

- A Nipoppy dataset with a valid global configuration file and an accurate manifest
    - See the [Quickstart guide](../quickstart.md) for instructions on how to set up a new dataset
- Raw imaging data in {{dpath_raw_imaging}}
    - See <project:populating.md>

### Data directories

| Directory | Content description |
|---|---|
| {{dpath_raw_imaging}} | **Input** -- {{content_dpath_raw_imaging}} |
| {{dpath_sourcedata}} | **Output** -- {{content_dpath_sourcedata}} |

### Commands

- Command-line interface: [`nipoppy reorg`](<project:../cli_reference/reorg.md>)
- Python API: {class}`nipoppy.workflows.DicomReorgWorkflow`

### Workflow

1. Nipoppy will loop over all participants/sessions that *have* data in {{dpath_raw_imaging}} but *do not have* data in {{dpath_sourcedata}} according to the {term}`doughnut file`
    - If the doughnut file does not exist, it will be automatically generated
    - If there is an existing doughnut file but it does not have all the rows in the manifest, new entries will be automatically added to the doughnut file
    - The doughnut file can also be completely regenerated with [`nipoppy doughnut --regenerate`](../cli_reference/doughnut.md)
2. For each participant-session pair:
    1. Files from the {{dpath_raw_imaging}} directory will be "copied" (the default is to create symlinks) to the {{dpath_sourcedata}} directory into a flat list
    2. The doughnut file is updated to indicate that this participant-session pair now has data in {{dpath_sourcedata}}

## Configuring the reorganization

By default, Nipoppy expects "participant-first" organization, like the following:
```{literalinclude} ./inserts/default_dicom_reorg-before.txt
```

All files in participant-session subdirectories (and sub-subdirectories, if applicable) will be reorganized under {{dpath_sourcedata}}`/sub-<PARTICIPANT_ID>/ses-<SESSION_ID>` (note the addition of BIDS prefixes), creating a flat list of files, like this:
```{literalinclude} ./inserts/default_dicom_reorg-after.txt
```

By default, the output files will be relative symbolic links ("symlinks") to avoid duplication of files.

If `"DICOM_DIR_PARTICIPANT_FIRST"` is set to `"false"` in the {term}`global configuration file <DICOM_DIR_PARTICIPANT_FIRST>`, then Nipoppy will instead expect session-level directories with nested participant-level directories (e.g., {{dpath_raw_imaging}}`/1/01` for the above example).

(dicom-dir-map-example)=
If the raw imaging data is not organized in any of these two structures, a custom comma-separated file can be created to map each unique participant-session pair to a directory path (relative to {{dpath_raw_imaging}}). This path to this mapping file must be specified in the `"DICOM_DIR_MAP_FILE"` in the {term}`global configuration file <DICOM_DIR_MAP_FILE>`. See the {ref}`schema reference <dicom-dir-map-schema>` for more information.

Here is an example file for a dataset that already uses the `ses-` prefix for sessions:

```{csv-table}
---
file: ../../../nipoppy/data/examples/sample_dicom_dir_map.csv
header-rows: 1
---
```

````{admonition} Raw content of the example DICOM directory mapping file
---
class: dropdown
---
```{literalinclude} ../../../nipoppy/data/examples/sample_dicom_dir_map.csv
---
linenos: True
language: csv
---
```
````

```{note}
More granular customization can also be achieved for both the input file paths and the output file names, see <project:#customizing-dicom-reorg>.
```

## Running the reorganization

### Using the command-line interface

```console
$ nipoppy reorg --dataset-root <DATASET_ROOT>
```

See the [CLI reference page](<project:../cli_reference/reorg.md>) for more information on optional arguments (e.g., reading DICOM headers to check the image type, and copying files instead of creating symlinks).

```{note}
Log files for this command will be written to {{dpath_logs}}`/dicom_reorg`
```

### Using the Python API

```python
from nipoppy.workflows import DicomReorgWorkflow

dpath_root = "."  # replace by path to dataset root directory
workflow = DicomReorgWorkflow(dpath_root=dpath_root)
workflow.run()
```

See the API reference for {class}`nipoppy.workflows.DicomReorgWorkflow` for more information on optional arguments (they correspond to the ones for the [CLI](<project:../cli_reference/reorg.md>)).

(customizing-dicom-reorg)=
#### Customizing input and output file paths

There may be datasets where the raw imaging files are not organized in a participant-session directory. An example of this would a dataset whose raw DICOM files are in archives, like so:
```{literalinclude} ./inserts/custom_dicom_reorg-before.txt
---
class: no-copybutton
---
```

In this case, using a DICOM directory mapping file as described above is not enough, since files from different imaging sessions are in the same directory.

The {class}`nipoppy.workflows.DicomReorgWorkflow` class exposes two functions for finer control of input paths and output filenames:
- {func}`nipoppy.workflows.DicomReorgWorkflow.get_fpaths_to_reorg` can be overridden to map a participant ID and session ID to a list of absolute filepaths to be reorganized
- {func}`nipoppy.workflows.DicomReorgWorkflow.apply_fname_mapping` can be overridden to rename output files
  - Note: output files will still be in the {{dpath_sourcedata}}`/sub-<PARTICIPANT_ID>/ses-<SESSION_ID>` directory

Here is an example of custom imaging data reorganization script:
```{literalinclude} ./inserts/custom_dicom_reorg.py
---
language: python
---
```

Running this script on the data shown above will create the following organized files (by default symlinks):
```{literalinclude} ./inserts/custom_dicom_reorg-after.txt
---
class: no-copybutton
---
```

## Next steps

Now that the raw imaging data has been organized in a standardized participant-session structure, it is ready for [BIDS conversion](./bids_conversion.md)!
