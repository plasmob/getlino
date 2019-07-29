from getlino import SETUP_INFO

from atelier.test import TestCase


class PackagesTests(TestCase):
    def test_01(self):
        self.run_packages_test(SETUP_INFO['packages'])
