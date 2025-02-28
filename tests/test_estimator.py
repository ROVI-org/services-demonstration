from typing import Callable

from pytest import raises
import msgpack

from roviweb.utils import load_variable


def test_load(est_file_path):
    # Wrong directory
    with raises(FileNotFoundError, match='No such file'):
        load_variable(est_file_path.read_text(), 'make_estimator')

    # Wrong variable name
    with raises(ValueError, match='not_found'):
        load_variable(est_file_path.read_text(), working_dir=est_file_path.parent, variable_name='not_found')

    est = load_variable(est_file_path.read_text(), working_dir=est_file_path.parent, variable_name='make_estimator')
    assert isinstance(est, Callable)


def test_several_steps(client, example_dataset, est_file_path, upload_estimator):
    # Register metadata
    example_dataset.metadata.name = 'module'
    client.post("/db/register", content=example_dataset.metadata.model_dump_json())

    # Upload a few steps of cycling data
    with client.websocket_connect("/db/upload/module") as websocket:
        # Send 4 data points
        for i in range(4):
            row = example_dataset.tables['raw_data'].iloc[i]
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
