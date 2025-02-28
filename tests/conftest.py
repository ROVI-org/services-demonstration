from shutil import copyfileobj
from pathlib import Path

import requests
from battdat.data import BatteryDataset
from pytest import fixture
from fastapi.testclient import TestClient

from roviweb.api import app
from roviweb.online import estimators
from roviweb.prognosis import forecasters
from roviweb.db import connect, list_batteries

_file_path = Path(__file__).parent / 'files'


@fixture()
def file_path() -> Path:
    return _file_path


@fixture()
def client():
    return TestClient(app)


@fixture()
def example_h5():
    url = 'https://data.materialsdatafacility.org/mdf_open/camp_2023/1.1/hdf5/refined/batch_B28A_cell_39.h5'
    h5_path = _file_path / 'example-h5.h5'
    if not h5_path.is_file():
        with h5_path.open('wb') as fp:
            copyfileobj(requests.get(url, stream=True).raw, fp)
    return h5_path


@fixture()
def example_dataset(example_h5):
    return BatteryDataset.from_hdf(example_h5)


@fixture(autouse=True)
def reset_status():
    conn = connect()
    for name in list_batteries():
        conn.execute(f'DROP TABLE IF EXISTS {name}')
        conn.execute(f'DROP TABLE IF EXISTS {name}_estimates')

    conn.execute('DELETE FROM battery_metadata')
    estimators.clear()
    forecasters.clear()


@fixture()
def est_file_path():
    return _file_path / 'diagnosis' / 'example-estimator.py'


@fixture()
def upload_estimator(est_file_path, client):
    """Register the online estimator"""
    with open(est_file_path.parent / 'initial-asoh.json', 'rb') as rb:
        return client.post('/online/register',
                           data={'name': 'module', 'definition': est_file_path.read_text(), 'start_time': 1.},
                           files=[('files', ('initial-asoh.json', rb))])
