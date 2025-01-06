"""Data models for interacting with web service"""
from pydantic import BaseModel


class TableStats(BaseModel):
    """Description of the contents of a table"""

    rows: int
    """Number of rows in the database"""
    columns: dict[str, str]
    """Names and types of the columns"""


def EstimatorStatus(BaseModel):
    """Condition and status of a state estimator"""

    state_names: list[str]
    """Names of each of the state"""
