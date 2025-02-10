"""Test HTML pages"""
from pathlib import Path
from shutil import rmtree

from battdat.data import BatteryDataset
from pytest import fixture
import msgpack

_views_dir = Path(__file__).parent / 'views'
rmtree(_views_dir, ignore_errors=True)
_views_dir.mkdir(exist_ok=True)


@fixture()
def add_data(client, example_h5):
    dataset = BatteryDataset.from_hdf(example_h5)
    with client.websocket_connect("/db/upload/module") as websocket:
        # Send 16 data points
        for i in range(16):
            row = dataset.tables['raw_data'].iloc[i]
            websocket.send_bytes(msgpack.packb(row.to_dict()))


@fixture()
def add_estimator(est_file_path, client):
    with open(est_file_path.parent / 'initial-asoh.json', 'rb') as rb:
        return client.post('/online/register',
                           data={'name': 'module', 'definition': est_file_path.read_text()},
                           files=[('files', ('initial-asoh.json', rb))])


def test_home(client):
    home_page = client.get('/')
    assert home_page.status_code == 200
    assert 'No data are available' in home_page.text


def test_not_found(client, example_h5):
    res = client.get('/dashboard/module')
    assert res.status_code == 404
    assert 'No such dataset: module' in res.text


def test_with_data(client, add_data):
    # Make sure it's present on the home page
    res = client.get('/')
    assert 'available for 1 batteries' in res.text

    # Test the dashboard
    res = client.get('/dashboard/module')
    assert res.status_code == 200
    assert 'No health estimates available' in res.text
    _views_dir.joinpath('dashboard.html').write_text(res.text)


def test_with_estimator(client, add_data, add_estimator):
    res = client.get('/dashboard/module')
    assert res.status_code == 200
    assert 'r0.base_values' in res.text


def test_history_figure(client, add_data):
    res = client.get('/dashboard/module/img/history.svg')
    assert res.status_code == 200
    _views_dir.joinpath('history.svg').write_text(res.text)
