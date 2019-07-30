from os.path import dirname, join
from atelier.test import TestCase
import getlino

class DockerTests(TestCase):
    def test_01(self):
        args = ['docker', 'build', '-t', 'getlino', join(dirname(getlino.__file__), '..')]
        self.run_subprocess(args)
