# Installation

Nipoppy is a Python package. We recommend installing it in a new or existing Python environment. The most common ways to create Python environments are through {term}`conda` and {term}`venv`.

```{note}
If you already have an existing Python environment setup, you can go directly to the [](#pip-install-section) section.
```

## Supported operating systems

The Nipoppy tools are primarily intended to be used on Linux operating system and may not work well on other operating systems. The default container platform used is Apptainer (formerly Singularity), which [cannot run natively on Windows or macOS](https://apptainer.org/docs/admin/main/installation.html#installation-on-windows-or-mac). Support for the Docker container platform has been added in 0.4.2, though users may need to change default container arguments that are Apptainer-specific.

(python-env-instructions)=
## Setting up a Python environment

```{tip}
If you do not already have Python set up on your system and/or wish to run Nipoppy locally, we recommend using {term}`conda`. However, {term}`venv` can be used by following the steps [here](https://docs.python.org/3/tutorial/venv.html#creating-virtual-environments).
```

### {term}`conda` setup

Install `conda` (e.g. through Miniconda) following instructions from [here](https://conda.io/projects/conda/en/latest/user-guide/install/index.html).

Create a new environment (if needed) with Python version of at least `3.9` (we recommended the [latest available version](https://www.python.org/doc/versions)). Here we call it `nipoppy_env`, but it can be named anything. In a Terminal window, run:
```{code-block} console
$ conda create --name nipoppy_env python=3
```

```{tip}
The [conda cheatsheet](https://docs.conda.io/projects/conda/en/latest/user-guide/cheatsheet.html) is a useful reference for the most commonly used `conda` commands.
```

Activate the environment, e.g. by running:
```{code-block} console
$ conda activate nipoppy_env
```

### {term}`venv` setup

*Note: These instructions assume you have an appropriate Python version installed.*

Create the Python virtual environment in a directory of your choice. Here we call it `nipoppy_env`, but it can be named anything. In a Terminal window, run:

```{code-block} console
$ python3 -m venv nipoppy_env
```

```{note}
If you have multiple versions of Python installed, you should specify which one to use (e.g. `python3.12` instead of `python3` in the previous command)
```

(pip-install-section)=
## Installing the `nipoppy` package

The latest release of Nipoppy can be installed from {term}`PyPI`. In a Terminal window, run:
```{code-block} console
$ pip install nipoppy
```

````{note}
You can also install the "bleeding-edge" development version of Nipoppy from GitHub directly:

```{code-block} console
$ pip install git+https://github.com/nipoppy/nipoppy.git@main
```

This version is **unstable**, and things could break without any notice. Use at your own risk.
````

````{note}
You can also install the optional terminal user interface of Nipoppy using
```{code-block} console
$ pip install "nipoppy[gui]"
```
The user interface is available with the `nipoppy-gui` command.
````

### Verifying the install

Nipoppy was installed successfully if the {term}`CLI` runs. The following command should print a usage message and exit without error:
```{code-block} console
$ nipoppy -h
```

### Enable shell completion
We list the configuration for `bash` and `zsh` shells. For more details on shell completion with Click, visit the official documentation at: https://click.palletsprojects.com/en/stable/shell-completion/

::::{tab-set}

:::{tab-item} Bash
Save the script somewhere.

```{code-block} console
$ _NIPOPPY_COMPLETE=bash_source nipoppy > ~/.nipoppy-complete.bash
```

Source the file in `~/.bashrc`.

```{code-block} console
$ . ~/.nipoppy-complete.bash
```

:::

:::{tab-item} Zsh
Save the script somewhere.

```{code-block} console
$ _NIPOPPY_COMPLETE=zsh_source nipoppy > ~/.nipoppy-complete.zsh
```

Source the file in `~/.zshrc`.

```{code-block} console
$ . ~/.nipoppy-complete.zsh
```

:::

::::

## Troubleshooting

Please open a [GitHub issue](https://github.com/nipoppy/nipoppy/issues/new/choose) for any error not covered below.

### Error when installing `pydantic-core`

The latest version of the `pydantic-core` package (required by `pydantic`) is written in Rust, not pure Python. If this package needs to be compiled during the install, but Rust is not available, then there might be an error complaining that Rust and/or Cargo cannot be found. In that case, if you are on an {term}`HPC` system that uses `lmod`, try loading Rust before installing:
```{code-block} console
$ module load rust
```

## Next steps

All done? See the [Quickstart guide](quickstart/index.md) next for instructions on how to set up a Nipoppy study and configure pipelines.
