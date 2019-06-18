from atelier.invlib import setup_from_tasks
ns = setup_from_tasks(
    globals(), "lino_getlino",
    languages="en de fr et nl es".split(),
    # tolerate_sphinx_warnings=True,
    blogref_url="http://lino-framework.org",
    revision_control_system='git')


