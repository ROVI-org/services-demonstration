"""Test forecasting ASOH values"""
import pandas as pd
import numpy as np
from pytest import fixture

from roviweb.utils import load_variable
from roviweb.schemas import PrognosticsFunction


@fixture()
def forecast_path(file_path):
    return file_path / 'prognosis' / 'example-forecaster.py'


def test_load_then_execute(forecast_path):
    forecast_fun: PrognosticsFunction = load_variable(forecast_path.read_text(), 'forecast', working_dir=forecast_path.parent)
    output = forecast_fun(
        pd.DataFrame({'q_t.base_values': np.random.normal(0.4, 0.005, size=(10000,))}),
        pd.DataFrame({'time': np.arange(200)})
    )
    assert len(output) == 200
