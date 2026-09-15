# Advanced configuration

This guide describes advanced configuration methods.

## Environment variables and `.env` files

Some {term}`CLI` options, such as `--layout`, can be configured via environment variables.
This will be indicated in the usage message when running `nipoppy <SUBCOMMAND> --help`.

It is also possible to set these options using `.env` environment files.
Nipoppy searches the following locations (in order of decreasing priority):
1. {{dpath_root}}`/.env`: study-level
2. `~/.nipoppy/.env`: user-level

The overall order for determining the value of options is as follows (highest to lowest priority):
1. Command-line options that are explicitly passed when calling the command
2. Environment variables that are already defined at runtime
3. Environment variables loaded from `.env` file(s) (see above)
4. CLI default values

(default-config-override)=
## Overriding the global configuration file

The default configuration file created by `nipoppy init` can be overridden by creating a user-level configuration file at {{fpath_user_config}}. This can enable the setting of certain machine- or user-specific fields, such as the container command. It can also allow the pre-definition of variables for common pipelines.

The `--default-config` CLI flag can be used to ignore the user-level file and force the use of the original default global configuration file.
