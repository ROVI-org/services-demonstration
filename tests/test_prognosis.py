"""Test forecasting ASOH values"""
from contextlib import ExitStack
from pathlib import Path

import pandas as pd
import numpy as np
from pytest import fixture

from roviweb.utils import load_variable
from roviweb.schemas import PrognosticsFunction, ForecasterInfo
from roviweb.prognosis import register_forecaster, list_forecasters

_my_query = 'SELECT q_t.base_values FROM $TABLE_NAME$ ORDER BY test_time DESC LIMIT 10000'


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
        sql_query=_my_query,
    )
    register_forecaster('cell', info)
    assert 'cell' in list_forecasters()


def upload_forecaster(path: Path, client):
    to_upload = path.parent.glob('*.pkl')
    with ExitStack() as stack:
        files = [(file.name, stack.enter_context(file.open('rb'))) for file in to_upload]
        return client.post('/prognosis/register',
                           data={'name': 'module',
                                 'definition': path.read_text(),
                                 'sql_query': _my_query},
                           files=[('files', f) for f in files])


def test_upload(forecast_path, client):
    result = upload_forecaster(forecast_path, client)
    assert result.status_code == 200, result.text
    assert _my_query in result.text
