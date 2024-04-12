"""Configuration file for the Sphinx documentation builder.

For the full list of built-in configuration values, see the documentation:
https://www.sphinx-doc.org/en/master/usage/configuration.html
"""

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

project = "Nipoppy"
copyright = "2024, NeuroDataScience-ORIGAMI Lab"
author = "NeuroDataScience-ORIGAMI Lab"

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = [
    "autoapi.extension",
    "myst_parser",
    "sphinxarg.ext",
    "sphinx.ext.autodoc",
    "sphinx.ext.autosummary",
    "sphinx.ext.intersphinx",
    # "sphinx.ext.linkcode",
    "sphinx.ext.napoleon",
    "sphinx.ext.autodoc.typehints",
]

templates_path = ["_templates"]
exclude_patterns = []


# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = "furo"
html_static_path = ["_static"]

# -- Intersphinx configuration ------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/extensions/intersphinx.html

intersphinx_mapping = {
    "pandas": ("https://pandas.pydata.org/pandas-docs/stable/", None),
    "pydantic": ("https://docs.pydantic.dev/latest/", None),
    "python": ("https://docs.python.org/3", None),
}

# -- Autodoc/AutoAPI configuration ----------------------------------------------------

autodoc_typehints = "description"

autoapi_dirs = ["../../nipoppy"]
autoapi_options = [
    "members",
    "undoc-members",
    # "private-members",
    "show-inheritance",
    # "show-module-summary",
    # "special-members",
    "imported-members",
]
autoapi_member_order = "groupwise"
autoapi_own_page_level = "class"
autoapi_template_dir = "_templates/autoapi"


# # TODO
# def linkcode_resolve(domain, info):
#     if domain != "py":
#         return None
#     if not info["module"]:
#         return None
#     filename = info["module"].replace(".", "/")
#     return f"https://github.com/""
