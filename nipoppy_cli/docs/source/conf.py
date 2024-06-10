"""Configuration file for the Sphinx documentation builder.

For the full list of built-in configuration values, see the documentation:
https://www.sphinx-doc.org/en/master/usage/configuration.html
"""

# for substitutions
from nipoppy.layout import DEFAULT_LAYOUT_INFO

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
    "sphinx_copybutton",
    "sphinx-jsonschema",
    "sphinx_togglebutton",
    "sphinx.ext.autodoc.typehints",
    "sphinx.ext.intersphinx",
    "sphinx.ext.napoleon",
]

templates_path = ["_templates"]
exclude_patterns = []

nitpicky = True

# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = "furo"
html_static_path = ["_static"]

# -- Furo configuration ------------------------------------------------------
#  https://pradyunsg.me/furo/customisation/#customisation
html_theme_options = {
    "source_repository": "https://github.com/neurodatascience/nipoppy",
    "source_branch": "main",
    "source_directory": "nipoppy_cli/docs/source",
}

# -- Intersphinx configuration ------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/extensions/intersphinx.html

intersphinx_mapping = {
    "pandas": ("https://pandas.pydata.org/pandas-docs/stable/", None),
    "pydantic": ("https://docs.pydantic.dev/latest/", None),
    "python": ("https://docs.python.org/3", None),
}

# -- MyST configuration -------------------------------------------------------

myst_enable_extensions = ["fieldlist", "substitution"]

myst_substitutions = {
    "fpath_manifest": f"`{DEFAULT_LAYOUT_INFO.fpath_manifest}`",
    "fpath_config": f"`{DEFAULT_LAYOUT_INFO.fpath_config}`",
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

# ignore some auto doc related warnings
#  see https://github.com/sphinx-doc/sphinx/issues/10785
nitpick_ignore = [
    ("py:class", "Path"),
    ("py:class", "optional"),
    ("py:class", "pd.DataFrame"),
    ("py:class", "bids.BIDSLayout"),
    ("py:class", "argparse.HelpFormatter"),
    ("py:class", "argparse._SubParsersAction"),
    ("py:class", "argparse._ActionsContainer"),
    ("py:class", "StrOrPathLike"),
    ("py:class", "nipoppy.utils.StrOrPathLike"),
    ("py:class", "typing_extensions.Self"),
]

# -- Copybutton configuration -------------------------------------------------
copybutton_exclude = ".linenos, .gp"

# -- JSON Schema configuration ------------------------------------------------
jsonschema_options = {
    "lift_definitions": True,
    "auto_reference": True,
    "auto_target": True,
}

# # TODO
# def linkcode_resolve(domain, info):
#     if domain != "py":
#         return None
#     if not info["module"]:
#         return None
#     filename = info["module"].replace(".", "/")
#     return f"https://github.com/""
