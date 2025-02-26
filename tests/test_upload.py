from roviweb.db import get_metadata
import msgpack


def test_upload(client):
    # Send a single row of data
    with client.websocket_connect("/db/upload/module") as websocket:
        websocket.send_bytes(msgpack.packb({'a': 1, 'b': 1.}))

    stats = client.get('/db/stats').json()
    assert not stats['module']['has_metadata']
    assert stats['module']['has_data']
    assert stats['module']['data_stats']['rows'] == 1
    assert stats['module']['data_stats']['columns'] == {'a': 'INTEGER', 'b': 'FLOAT', 'received': 'FLOAT'}


def test_upload_bulk(client):
    records = [{'a': 1, 'b': 1}]

    assert client.post('/db/upload/module', json=[]).json() == 0
    assert client.post('/db/upload/module', json=records).json() == 1


def test_upload_metadata(client, example_dataset):
    res = client.post('/db/register', content=example_dataset.metadata.model_dump_json())
    assert res.status_code == 200
    assert res.json() == example_dataset.metadata.name

    stats = client.get('/db/stats').json()
    name = res.json()
    assert stats[name]['has_metadata']
    assert not stats[name]['has_estimator']
    assert not stats[name]['has_data']

    metadata = get_metadata(name)
    assert metadata.name == name
