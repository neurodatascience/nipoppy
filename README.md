# Nipoppy

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.8084759.svg)](https://doi.org/10.5281/zenodo.8084759)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](https://opensource.org/license/mit)
[![codecov](https://codecov.io/gh/neurodatascience/nipoppy/graph/badge.svg?token=SN38ITRO4M)](https://codecov.io/gh/neurodatascience/nipoppy)
[![https://github.com/psf/black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://black.readthedocs.io/en/stable/)
[![Documentation Status](https://readthedocs.org/projects/nipoppy/badge/?version=latest)](https://nipoppy.readthedocs.io/en/latest/?badge=latest)

Nipoppy is a lightweight framework for standardized organization and processing of neuroimaging-clinical datasets. Its goal is to help users adopt the
[FAIR](https://www.go-fair.org/fair-principles/) principles
and improve the reproducibility of studies.

The framework includes three components:

1. A protocol for data organization, curation and processing, with steps that include the following:
    - **Organization** of raw data, including conversion of raw DICOMs (or NIfTIs) to [BIDS](https://bids.neuroimaging.io/)
    - **Processing** of imaging data with existing or custom pipelines
    - **Tracking** of data availability and processing status
    - **Extraction** of imaging-derived phenotypes (IDPs) for downstream statistical modelling and analysis

    ![Nipoppy protocol](nipoppy_cli/docs/source/_static/img/nipoppy_protocol.jpg)

2. A specification for dataset organization that extends the [Brain Imaging Data Structure (BIDS) standard](https://bids.neuroimaging.io/) by providing additional guidelines for tabular (e.g., phenotypic) data and imaging derivatives.

    ![Nipoppy specification](nipoppy_cli/docs/source/_static/img/nipoppy_specification.jpg)

3. A **command-line interface** and **Python package** that provide user-friendly tools for applying the framework. The tools build upon existing technologies such as the [Apptainer container platform](https://apptainer.org/) and the [Boutiques descriptor framework](https://boutiques.github.io/). Several existing containerized pipelines are supported out-of-the-box, and new pipelines can be added easily by the user.
    - We have also developed a [**web dashboard**](https://digest.neurobagel.org) for interactive visualizations of imaging and phenotypic data availability.

See the [documentation website](https://neurobagel.org/nipoppy/overview/) for more information!
