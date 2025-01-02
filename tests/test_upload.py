import msgpack
from pytest import fixture
from fastapi.testclient import TestClient

from roviweb.api import app


@fixture()
def client():
    return TestClient(app)


def test_connect(client):
    with client.websocket_connect("/upload") as websocket:
        websocket.send_json({"name": "module"})
        msg = websocket.receive_json()
        assert msg['success'] and msg['message'].endswith('module')


def test_connect_failure(client):
    with client.websocket_connect("/upload") as websocket:
        websocket.send_json({})
        msg = websocket.receive_json()
        assert not msg['success'] and 'name' in msg['reason']


def test_upload(client):
    with client.websocket_connect("/upload") as websocket:
        websocket.send_json({"name": "module"})
        websocket.receive_json()

        # Send the first data
        websocket.send_bytes(msgpack.packb({'a': 1, 'b': 1.}))
    stats = client.get('/dbstats').json()
    assert stats['module']['columns'] == {'a': 'INTEGER', 'b': 'FLOAT'}
