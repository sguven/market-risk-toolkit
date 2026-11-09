import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import pytest

from xvalab import USD_SOFR, ExposureEngine, InterestRateSwap, NettingSet, default_model


@pytest.fixture(scope="session")
def engine():
    return ExposureEngine(default_model(), n_paths=4000, seed=11)


@pytest.fixture(scope="session")
def payer_10y():
    return InterestRateSwap(100e6, USD_SOFR.swap_rate(0, 10), 10.0, True, name="10y payer")


@pytest.fixture(scope="session")
def payer_exposure(engine, payer_10y):
    return engine.run(NettingSet([payer_10y], None, "payer"))
