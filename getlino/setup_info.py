SETUP_INFO = dict(
    name='getlino',
    version='19.7.2',
    install_requires=['click', 'virtualenv', 'cookiecutter', 'atelier'],
    test_suite='tests',
    description="Lino installer",
    long_description=u"""
    Configure a Lino server and create sites on it.
    """,
    author='Rumma & Ko Ltd',
    author_email='team@lino-framework.org',
    url="http://lino-framework.org",
    license='BSD-2-Clause',
    entry_points={
        'console_scripts': ['getlino = getlino.cli:main']
    },

    classifiers="""\
Programming Language :: Python :: 3
Development Status :: 1 - Planning
Environment :: Console
Framework :: Django
Intended Audience :: Developers
Intended Audience :: System Administrators
License :: OSI Approved :: BSD License
Operating System :: OS Independent
Topic :: System :: Installation/Setup
Topic :: Software Development :: Libraries :: Python Modules
""".splitlines())

SETUP_INFO.update(
    zip_safe=False,
    include_package_data=True)

SETUP_INFO.update(packages=[n for n in """
getlino
""".splitlines() if n])
