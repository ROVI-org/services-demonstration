"""Test forecasting ASOH values"""
import pandas as pd
import numpy as np
from pytest import fixture

from roviweb.utils import load_variable
from roviweb.schemas import PrognosticsFunction, ForecasterInfo
from roviweb.prognosis import register_forecaster, list_forecasters


@fixture()
def forecast_path(file_path):
    return file_path / 'prognosis' / 'example-forecaster.py'


@fixture()
def forecast_fun(forecast_path) -> PrognosticsFunction:
    return load_variable(forecast_path.read_text(), 'forecast', working_dir=forecast_path.parent)


def test_load_then_execute(forecast_fun):
    output = forecast_fun(
        pd.DataFrame({'q_t.base_values': np.random.normal(0.4, 0.005, size=(10000,))}),
        pd.DataFrame({'time': np.arange(200)})
    )
    assert len(output) == 200


def test_register(forecast_fun):
    info = ForecasterInfo(
        function=forecast_fun,
        sql_query='SELECT q_t.base_values FROM $TABLE_NAME$ ORDER BY test_time DESC LIMIT 10000',
    )
    register_forecaster('cell', info)
    assert 'cell' in list_forecasters()
