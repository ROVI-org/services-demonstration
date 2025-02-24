"""Test forecasting ASOH values"""
from contextlib import ExitStack
from pathlib import Path

import msgpack
import pandas as pd
import numpy as np
from pytest import fixture

from roviweb.utils import load_variable
from roviweb.schemas import PrognosticsFunction, ForecasterInfo, LoadSpecification
from roviweb.prognosis import register_forecaster, list_forecasters

_my_query = 'SELECT test_time,q_t__base_values FROM $TABLE_NAME$ ORDER BY test_time DESC LIMIT 10000'


@fixture()
def forecast_path(file_path):
    return file_path / 'prognosis' / 'example-forecaster.py'


@fixture()
def forecast_fun(forecast_path) -> PrognosticsFunction:
    return load_variable(forecast_path.read_text(), 'forecast', working_dir=forecast_path.parent)


def test_load_then_execute(forecast_fun):
    output = forecast_fun(
        pd.DataFrame({'q_t__base_values': np.random.normal(0.4, 0.005, size=(10000,))}),
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


def test_run(forecast_fun, example_dataset, upload_estimator, client):
    # Register the forecaster
    info = ForecasterInfo(
        function=forecast_fun,
        sql_query=_my_query,
    )
    register_forecaster('module', info)

    # Upload a few steps of cycling data
    with client.websocket_connect("/db/upload/module") as websocket:
        # Send 4 data points
        for i in range(10001):
            row = example_dataset.tables['raw_data'].iloc[i]
            websocket.send_bytes(msgpack.packb(row.to_dict()))

    reply = client.get('/prognosis/module/run', params=LoadSpecification(ahead_time=1000).model_dump())
    df = pd.DataFrame(reply.json())
    assert len(df) == 1000
    assert 'q_t__base_values' in df.columns

    reply = client.get('/dashboard/module/img/forecast.svg', params=LoadSpecification(ahead_time=10000).model_dump())
    assert reply.status_code == 200, reply.text
    Path(__file__).parent.joinpath('views/forecast.svg').write_text(reply.text)
