from battdat.data import BatteryDataset
from moirae.estimators.online.joint import JointEstimator
from pytest import raises
import msgpack

from roviweb.utils import load_variable


def upload_estimator(path, client):
    with open(path.parent / 'initial-asoh.json', 'rb') as rb:
        return client.post('/online/register',
                           data={'name': 'module', 'definition': path.read_text()},
                           files=[('files', ('initial-asoh.json', rb))])


def test_load(est_file_path):
    # Wrong directory
    with raises(FileNotFoundError, match='No such file'):
        load_variable(est_file_path.read_text(), 'estimator')

    # Wrong variable name
    with raises(ValueError, match='not_found'):
        load_variable(est_file_path.read_text(), working_dir=est_file_path.parent, variable_name='not_found')

    est = load_variable(est_file_path.read_text(), working_dir=est_file_path.parent, variable_name='estimator')
    assert isinstance(est, JointEstimator)


def test_upload(client, est_file_path):
    """Test a successful upload"""
    result = upload_estimator(est_file_path, client)
    assert result.status_code == 200, result.text


def test_several_steps(client, example_h5, est_file_path):
    # Make the client and load dataset
    upload_estimator(est_file_path, client)
    dataset = BatteryDataset.from_hdf(example_h5)

    # Upload a few steps of cycling data
    with client.websocket_connect("/db/upload/module") as websocket:
        # Send 4 data points
        for i in range(4):
            row = dataset.tables['raw_data'].iloc[i]
            websocket.send_bytes(msgpack.packb(row.to_dict()))

    # Pull the estimator status
    result = client.get('/online/status')
    assert result.status_code == 200, result.text
    state = result.json()
    assert 'module' in state
    assert state['module']['latest_time'] == row['test_time']

    # Check the table status
    datasets = client.get('/db/status').json()
    assert len(datasets) == 1
