# -*- coding: UTF-8 -*-
# Copyright 2014-2019 Rumma & Ko Ltd
# License: BSD (see file COPYING for details)

SETUP_INFO = dict(
    name='lino-getlino',
    version='19.6.0',
    install_requires=['argh'],
    test_suite='tests',
    description="Get Lino application",
    long_description=u"""
    Get Lino application
    """,
    author='Luc Saffre',
    author_email='luc.saffre@gmail.com',
    url="http://lino-framework.org",
    license='BSD License',
    package_dir={'lino_getlino': 'lino_getlino'},
    entry_points={
        'console_scripts': [
            'lino_getlino = scripts.lino.__main__:main',
        ]
    },
    classifiers="""\
Programming Language :: Python
Programming Language :: Python :: 3
Development Status :: 1 - Planning
Environment :: Web Environment
Framework :: Django
Intended Audience :: Developers
Intended Audience :: System Administrators
License :: OSI Approved :: BSD License
Operating System :: OS Independent
Topic :: Office/Business :: Financial :: Accounting
""".splitlines())

SETUP_INFO.update(
    zip_safe=False,
    include_package_data=True)