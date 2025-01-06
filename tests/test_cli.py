from functools import partial
from urllib import parse

from pytest import raises, fixture

from roviweb.cli import main


@fixture(autouse=True)
def mock_web_service(mocker, client):
    # Make a function which mocks URL
    def _call_test(my_method, url, *args, **kwargs):
        path = parse.urlparse(url)
        return client.request(my_method, path.path, *args, **kwargs)

    for method in ['post', 'get']:
        mocker.patch(
            f'roviweb.cli.httpx.{method}',
            partial(_call_test, method)
        )

    # Wrap the websocket function
    def _call_ws(url):
        path = parse.urlparse(url)
        return client.websocket_connect(path.path)

    mocker.patch('roviweb.cli.connect_ws', _call_ws)


def test_help(capsys):
    with raises(SystemExit):
        main(['--url', 'testservice', '--help'])
    captured = capsys.readouterr()
    assert 'Register a state estimator' in captured.out


def test_upload(file_path, capsys, example_h5):
    # Send a model in
    main([
        'register', 'module',
        str(file_path / 'example-estimator.py'),
        str(file_path / 'initial-asoh.json')
    ])
    assert 'Received a JointEstimator for data_source=module' in capsys.readouterr().out

    # Check if it's available
    main(['status'])
    assert 'Estimator for module:' in capsys.readouterr().out

    # Send 4 steps of data
    main([
        'upload', 'module',
        '--max-to-upload', '4',
        str(example_h5)
    ])

    # Print the status again
    main(['status'])
    assert '  module: 4' in capsys.readouterr().out


def test_status(capsys):
    main(['status'])
    assert 'No databases available' in capsys.readouterr().out
