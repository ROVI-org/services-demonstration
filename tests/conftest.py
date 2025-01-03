from pytest import fixture
from fastapi.testclient import TestClient

from roviweb.api import app


@fixture()
def client():
    return TestClient(app)
