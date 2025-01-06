"""Data models for interacting with web service"""
from pydantic import BaseModel


class TableStats(BaseModel):
    """Description of the contents of a table"""

    rows: int
    """Number of rows in the database"""
    columns: dict[str, str]
    """Names and types of the columns"""


class EstimatorStatus(BaseModel):
    """Condition and status of a state estimator"""

    state_names: list[str]
    """Names of each of the state"""
    latest_time: float
    """Test time to which state corresponds to"""
    mean: list[float]
    """Mean of the state estimates"""
    covariance: list[list[float]]
    """Covariance of the estimated states"""
