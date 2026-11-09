import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import pytest

from vclab import SPX_SURFACE, example_book, simulate_factor_returns


@pytest.fixture(scope="session")
def surface():
    return SPX_SURFACE


@pytest.fixture(scope="session")
def book(surface):
    return example_book(surface.spot, surface)


@pytest.fixture(scope="session")
def history():
    return simulate_factor_returns()
