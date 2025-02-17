"""Utilities used in multiple modules"""
from contextlib import chdir
from pathlib import Path


def load_variable(text: str, variable_name: str = 'estimator', working_dir: Path | None = None):
    """Executing a Python file and retrieving a single variable

    The file should be executed in a directory containing any of the files provided alongside the estimator.

    Args:
        text: Text of a Python file to be executed
        variable_name: Name of variable to be retrieved
        working_dir: Directory in which to execute Python file
    Returns:
        The target object
    """

    with chdir(working_dir if working_dir is not None else Path.cwd()):
        spec_ns = {}
        exec(text, spec_ns)
        if variable_name not in spec_ns:
            raise ValueError(f'Variable "{variable_name}" not found in')

        return spec_ns[variable_name]
