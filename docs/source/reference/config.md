# The global configuration file

See {ref}`here<config-schema>` for the auto-generated schema for the global configuration file.

## Imaging data organization

Fields for specifying the path to participant-session data directories in {{dpath_pre_reorg}}. Note that these two options are mutually exclusive (cannot both be specified).

```{note}
By default, BIDS prefixes (i.e., `sub-` and `ses-`) are not expected in {{dpath_pre_reorg}} subdirectory names, though this can be customized if needed (see {ref}`here <dicom-dir-map-schema>` for more information).
```

```{glossary}
`DICOM_DIR_PARTICIPANT_FIRST`
    Can be set to `false` to indicate that the data is organized in subdirectories following the {{dpath_pre_reorg}}`/<SESSION_ID>/<PARTICIPANT_ID>` pattern. Otherwise, setting to `true` is equivalent to the default (files in {{dpath_pre_reorg}}`/<PARTICIPANT_ID>/<SESSION_ID>` directories).

`DICOM_DIR_MAP_FILE`
    Explicit mapping file for more custom directory names. See {ref}`here <dicom-dir-map-example>` for an example and {ref}`here <dicom-dir-map-schema>` for the auto-generated schema.
```

## Imaging data processing

Fields for configuring image processing pipelines, container runtimes, and high-performance computing jobs.

```{glossary}
`CONTAINER_CONFIG`
    Configuration options for the container runtime. This is the top-level configuration, which will be inherited by any downstream container configurations unless they set the `INHERIT` to `false`.

    The configuration options include the command to call the container executable, command-line arguments, and environment variables. See [here](<config-schema>) for the auto-generated schema.

`HPC_PREAMBLE`
    Command(s) to include at the top of the {term}`HPC` job submission file

`HPC_QUEUE_LIMIT`
    Maximum number of jobs allowed in the {term}`HPC` queue per user. This limit varies based on {term}`HPC` systems.

`PIPELINE_VARIABLES`
    Study-specific configurations for individual pipelines. This section is populated as needed when new pipelines are installed.
```

## Other

Miscellaneous fields.

```{glossary}
`SUBSTITUTIONS`
    A user-defined string replacement mapping. For each key-value pair, every instance of the key will be replaced by its corresponding value when the global configuration file is loaded. These substitutions will also be applied to downstream configuration files (e.g., invocation files).

`CUSTOM`
    Free field (though must be a dictionary). The global configuration file does not allow custom fields (i.e. that are not part of the schema) at the top level of the file, but users who wish to include additional fields may do so under `CUSTOM`.
```
