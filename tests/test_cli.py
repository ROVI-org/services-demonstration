from functools import partial
from urllib import parse

from pytest import raises, fixture, mark

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
    assert 'Functions associated with diagnosing battery health' in captured.out


@mark.parametrize('clock_factor', [None, '1e6'])
def test_upload(file_path, capsys, example_h5, clock_factor):
    # Send a model in
    main([
        'diagnosis', 'register', 'module',
        str(file_path / 'example-estimator.py'),
        str(file_path / 'initial-asoh.json')
    ])
    assert 'for data_source=module. Response="JointEstimator"' in capsys.readouterr().out

    # Check if it's available
    main(['status'])
    assert 'Estimator for module:' in capsys.readouterr().out

    # Send 4 steps of data
    main([
             'upload', 'module',
             '--max-to-upload', '4',
         ] + (
             [] if clock_factor is None else ['--clock-factor', clock_factor]
         ) + [
             '--report-freq', '2',
             str(example_h5)
         ])

    # Print the status again
    main(['status'])
    assert '  module: 4' in capsys.readouterr().out


def test_register_prognosis(file_path, capsys):
    main([
             'prognosis', 'register', 'module',
             str(file_path / 'prognosis' / 'example-forecaster.py'),
             'SELECT test_time, q_t__base_values FROM $TABLE_NAME$',
         ] + list(map(str, file_path.joinpath('prognosis').glob('*.pkl'))))
    assert 'for data_source=module. Response="sql_query' in capsys.readouterr().out


def test_status(capsys):
    main(['status'])
    assert 'No batteries available' in capsys.readouterr().out
