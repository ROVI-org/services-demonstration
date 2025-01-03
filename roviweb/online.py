"""Functions for managing online estimation"""
import dataclasses
from contextlib import chdir
from pathlib import Path

from moirae.estimators.online import OnlineEstimator


def load_estimator(text: str, variable_name: str = 'estimator', working_dir: Path | None = None) -> OnlineEstimator:
    """Load an estimator by executing a Python file and retrieving a single variable

    The file should be executed in a directory containing any of the files provided alongside the estimator.

    Args:
        text: Text of a Python file to be executed
        variable_name: Name of variable to be retrieved
        working_dir: Directory in which to execute Python file
    Returns:
        The online estimator implemented in the file
    """

    with chdir(working_dir if working_dir is not None else Path.cwd()):
        spec_ns = {}
        exec(text, spec_ns)
        if variable_name not in spec_ns:
            raise ValueError(f'Variable "{variable_name}" not found in')

        return spec_ns[variable_name]


@dataclasses.dataclass
class EstimatorHolder:
    """Class which holds the estimator and data about its progress"""

    estimator: OnlineEstimator
    """Estimator being propagated"""
    last_time: float
    """Test time at which the states are estimated"""
