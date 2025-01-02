from pytest import fixture
from fastapi.testclient import TestClient

from roviweb.api import app


@fixture()
def client():
    return TestClient(app)


def test_connect(client):
    with client.websocket_connect("/upload") as websocket:
        websocket.send_json({"name": "module-1"})
        msg = websocket.receive_json()
        assert msg['success'] and msg['message'].endswith('module-1')


def test_connect_failure(client):
    with client.websocket_connect("/upload") as websocket:
        websocket.send_json({})
        msg = websocket.receive_json()
        assert not msg['success'] and 'name' in msg['reason']
