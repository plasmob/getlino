import sys
if sys.version_info[0] < 3:
    raise Exception("Requires Python 3")

from setuptools import setup


SETUP_INFO = dict(
    name='getlino',
    version='19.7.2',
    install_requires=['click', 'virtualenv', 'cookiecutter'],
    # install_requires=['click', 'virtualenv', 'cookiecutter', 'setuptools', 'uwsgi'],
    test_suite='tests',
    description="Get Lino application",
    long_description=u"""
    Configure a Lino production server and create sites on it.
    """,
    author='Rumma & Ko Ltd',
    author_email='team@lino-framework.org',
    url="http://lino-framework.org",
    license='BSD-2-Clause',
    scripts=['getlino.py'],
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

if __name__ == '__main__':
    setup(**SETUP_INFO)
