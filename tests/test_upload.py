import msgpack


def test_upload(client):
    # Send a single row of data
    with client.websocket_connect("/db/upload/module") as websocket:
        websocket.send_bytes(msgpack.packb({'a': 1, 'b': 1.}))

    stats = client.get('/db/stats').json()
    assert stats['module']['rows'] == 1
    assert stats['module']['columns'] == {'a': 'INTEGER', 'b': 'FLOAT', 'received': 'FLOAT'}


def test_upload_metadata(client, example_dataset):
    res = client.post('/db/register', content=example_dataset.metadata.model_dump_json())
    assert res.status_code == 200
    assert res.json() == example_dataset.metadata.name
