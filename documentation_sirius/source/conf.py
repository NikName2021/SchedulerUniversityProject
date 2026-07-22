project = 'Система расписания для Университета «Сириус»'
copyright = '2026, Университет «Сириус»'
author = 'Университет «Сириус»'
release = '1.0'

extensions = [
    'myst_parser',
    'sphinx.ext.autosectionlabel',
]

language = 'ru'
html_theme = 'sphinx_rtd_theme'
html_title = project
html_static_path = ['_static']
html_css_files = ['custom.css']
templates_path = ['_templates']
exclude_patterns = ['_build']
autosectionlabel_prefix_document = True
