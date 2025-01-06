from shutil import copyfileobj
from pathlib import Path

import requests
from pytest import fixture
from fastapi.testclient import TestClient

from roviweb.api import app, conn, estimators, known_datasets

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


@fixture(autouse=True)
def reset_status():
    conn.execute('DROP TABLE IF EXISTS module')
    estimators.clear()
    known_datasets.clear()
