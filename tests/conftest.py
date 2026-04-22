"""Global test configuration and fixtures."""

import os

from tests import TEST_API_KEY

os.environ["API_KEY"] = TEST_API_KEY
