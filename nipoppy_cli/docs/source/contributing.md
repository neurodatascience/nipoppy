# Contributing

Nipoppy is under active development, and we welcome outside contributions!

Please report bugs or start a conversation about potential enhancements/new features by opening a new [GitHub issue](https://github.com/nipoppy/nipoppy/issues/new).

## Developer setup

Fork the [repository](https://github.com/nipoppy/nipoppy) on GitHub, then clone it and **install it with `dev` dependencies**, following instructions from [here](#github-install-section).

Set up [`pre-commit`](https://pre-commit.com/) to apply automatic formatting/linting/etc. when making a new commit:
```{code-block} console
$ pre-commit install
```

## Running the test suite

Within the root directory of the repo, run:
```{code-block} console
$ python -m pytest
```

## Building the documentation

Move the the `docs` directory:
```{code-block} console
$ cd docs
```

Run:
```{code-block} console
$ make html
```

Then open the `build/html/index.html` file in a browser.
