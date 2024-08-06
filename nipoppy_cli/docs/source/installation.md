(installation-instructions)=
# Installation

Nipoppy is a Python package. We recommend installing it in a new or existing Python environment. The most common ways to create Python environments are through {term}`conda` and {term}`venv`.

```{note}
If you already have an existing Python environment setup, you can go directly to the [](#pip-install-section) section.
```

## Supported operating systems

The Nipoppy tools are intended to be used on Linux operating system, and may not work on other operating systems. All processing pipelines with built-in support in Nipoppy are assumed to use Apptainer (formerly Singularity), which [cannot run natively on Windows or macOS](https://apptainer.org/docs/admin/main/installation.html#installation-on-windows-or-mac). Support for the Docker container platform may eventually be added, though that is not a priority at the moment.

## Setting up a Python environment

```{tip}
If you do not already have Python set up on your system and/or wish to run Nipoppy locally, we recommend using {term}`conda` instead of {term}`venv`.
```

### {term}`conda` setup

Install `conda` (e.g. through Miniconda) following instructions from [here](https://conda.io/projects/conda/en/latest/user-guide/install/index.html).

Create a new environment (if needed) with Python version of at least `3.9`. Here we call it `nipoppy_env`, but it can be named anything. In a Terminal window, run:
```{code-block} console
$ conda create --name nipoppy_env python=3.12
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
$ python -m venv nipoppy_env
```

```{note}
If you have multiple versions of Python installed, you should specify which one to use (e.g. `python3.12` instead of `python` in the previous command)
```

````{admonition} On Compute Canada/Digital Research Alliance of Canada systems
---
class: dropdown
---
If you are using one of the [Compute Canada/Digital Research Alliance of Canada](https://docs.alliancecan.ca/wiki/Technical_documentation) {term}`HPC` systems, you should instead use `virtualenv`:
```{code-block} console
$ virtualenv --no-download nipoppy_env
```

See the [Compute Canada wiki](https://docs.alliancecan.ca/wiki/Python#Creating_and_using_a_virtual_environment) for more information.
````

Activate the virtual environment, e.g. by running:
```{code-block} console
$ source nipoppy_env/bin/activate
```

(pip-install-section)=
## Installing the `nipoppy` package

### From {term}`PyPI`

% TODO
We are actively working on publishing the package on PyPI, but for now it can only be installed by cloning the GitHub repository (see next section). Come back later for updates!

% The latest release of Nipoppy can be installed from {term}`PyPI`. In a Terminal window, run:
% ```{code-block} console
% $ pip install nipoppy
% ```

(github-install-section)=
### From GitHub

If you wish to use the latest (potentially unstable) version of the package, you can get it from the [GitHub repository](https://github.com/nipoppy/nipoppy).

Clone the repository in a directory of your choice:
```{code-block} console
$ git clone https://github.com/nipoppy/nipoppy.git
```

Move into that directory and the `nipoppy_cli` subdirectory:
```{code-block} console
$ cd nipoppy/nipoppy_cli
```

```{note}
The `nipoppy_cli` subdirectory contains the newer version of the code, which has been refactored into a CLI. Eventually, it will become the only maintained version of the code. For the moment, the soon-to-be legacy code is still at the top level of the GitHub repository.
```

Install from the local source code in editable mode:
```{code-block} console
$ pip install -e .
```

````{note}
You can also install the package with `dev` dependencies (e.g., for running tests and building documentation):
```{code-block} console
$ pip install -e '.[dev]'
```
````

### Verifying the install

% TODO replace with nipoppy --version once that is available
Nipoppy was installed successfully if the {term}`CLI` runs. The following command should print a usage message and exit without error:
```{code-block} console
$ nipoppy -h
```

## Troubleshooting

Please create a [GitHub issue](https://github.com/nipoppy/nipoppy/issues/new) for any error not covered below.

### Error when installing `pydantic-core`

The latest version of the `pydantic-core` package (required by `pydantic`) is written in Rust, not pure Python. If package needs to be compiled during the install, but Rust is not available, then there might be an error complaining that Rust and/or Cargo cannot be found. In that case, if you are on an {term}`HPC` system that uses `lmod`, try loading Rust before installing:
```{code-block} console
$ module load rust
```

## Next steps

All done? See the [Quickstart guide](quickstart) next for instructions on how to set up a Nipoppy dataset and configure pipelines.
