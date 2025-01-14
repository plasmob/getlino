import sys
if sys.version_info[0] < 3:
    raise Exception("Requires Python 3")

from setuptools import setup

fn = 'getlino/setup_info.py'
exec(compile(open(fn, "rb").read(), fn, 'exec'))

if __name__ == '__main__':
    setup(**SETUP_INFO)
