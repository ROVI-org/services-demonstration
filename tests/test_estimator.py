from pathlib import Path

from battdat.data import BatteryDataset
from moirae.estimators.online.joint import JointEstimator
from pytest import raises
import msgpack

from roviweb.online import load_estimator

_est_file_path = Path(__file__).parent / 'files' / 'example-estimator.py'


def upload_estimator(client):
    with open(_est_file_path.parent / 'initial-asoh.json', 'rb') as rb:
        return client.post('/online/register',
                           data={'name': 'module', 'definition': _est_file_path.read_text()},
                           files=[('files', ('initial-asoh.json', rb))])


def test_load():
    # Wrong directory
    with raises(FileNotFoundError, match='No such file'):
        load_estimator(_est_file_path.read_text())

    # Wrong variable name
    with raises(ValueError, match='not_found'):
        load_estimator(_est_file_path.read_text(), working_dir=_est_file_path.parent, variable_name='not_found')

    est = load_estimator(_est_file_path.read_text(), working_dir=_est_file_path.parent)
    assert isinstance(est, JointEstimator)


def test_upload(client):
    """Test a successful upload"""
    result = upload_estimator(client)
    assert result.status_code == 200, result.text


def test_several_steps(client, example_h5):
    # Make the client and load dataset
    upload_estimator(client)
    dataset = BatteryDataset.from_hdf(example_h5)

    # Upload a few steps of cycling data
    with client.websocket_connect("/upload") as websocket:
        websocket.send_json({"name": "module"})
        msg = websocket.receive_json()
        assert msg['success'] and msg['message'].endswith('module')

        # Send 4 data points
        for i in range(4):
            row = dataset.tables['raw_data'].iloc[i]
            websocket.send_bytes(msgpack.packb(row.to_dict()))
