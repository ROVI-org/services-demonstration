from pathlib import Path

from moirae.estimators.online.joint import JointEstimator
from pytest import raises

from roviweb.online import load_estimator

_est_file_path = Path(__file__).parent / 'files' / 'example-estimator.py'


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
    with open(_est_file_path.parent / 'initial-asoh.json', 'rb') as rb:
        result = client.post('/online/register',
                             data={'name': 'module', 'definition': _est_file_path.read_text()},
                             files=[('files', ('initial-asoh.json', rb))])
    assert result.status_code == 200, result.text
