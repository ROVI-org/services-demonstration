"""Test HTML pages"""
from battdat.data import BatteryDataset
import msgpack


def test_home(client):
    home_page = client.get('/')
    assert home_page.status_code == 200


def test_display_panel(client, example_h5):
    res = client.get('/dashboard/module')
    assert res.status_code == 404
    assert 'No such dataset: module' in res.text

    # Upload some data
    dataset = BatteryDataset.from_hdf(example_h5)
    with client.websocket_connect("/db/upload/module") as websocket:
        # Send 16 data points
        for i in range(16):
            row = dataset.tables['raw_data'].iloc[i]
            websocket.send_bytes(msgpack.packb(row.to_dict()))

    res = client.get('/dashboard/module')
    assert res.status_code == 200
    assert 'No health estimates available' in res.text
