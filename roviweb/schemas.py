"""Data models for interacting with web service"""
import numpy as np
from typing import Callable

import pandas as pd

from pydantic import BaseModel, Field


class TableStats(BaseModel):
    """Description of the contents of a table"""

    rows: int
    """Number of rows in the database"""
    columns: dict[str, str]
    """Names and types of the columns"""


class BatteryStats(BaseModel):
    """Describe the status of a certain battery"""

    has_metadata: bool
    """Whether metadata have been registered for the cell"""
    has_data: bool
    """Whether a dataset for the cell has been uploaded"""
    has_estimator: bool
    """Whether an estimator is available for the cell"""

    # About the dataaset
    data_stats: TableStats | None
    """Description of the table"""


class EstimatorStatus(BaseModel):
    """Condition and status of a state estimator"""

    is_ready: bool
    """Whether we have acquired enough data to start estimation"""
    state_names: list[str] = ()
    """Names of each of the state"""
    latest_time: float = np.nan
    """Test time to which state corresponds to"""
    mean: list[float] = ()
    """Mean of the state estimates"""
    covariance: list[list[float]] = ((),)
    """Covariance of the estimated states"""


PrognosticsFunction = Callable[[pd.DataFrame, pd.DataFrame], pd.DataFrame]
"""Interface for functions which predict future aSOH given past estimates"""


class ForecasterInfo(BaseModel):
    """Information about how to run the prognosis models"""

    function: PrognosticsFunction = Field(repr=False)
    """Function to be invoked for inferring prognosis"""
    sql_query: str = Field(pattern=r'(?:from|FROM) \$TABLE_NAME\$')
    """Query used against the time series database to gather inference inputs"""
    output_names: list[str] | None = None
    """Names of the columns output by the estimator"""


RecordType = dict[str, int | float | str]
"""Accepted format for DB records"""


class LoadSpecification(BaseModel):
    """Specification used for load forecasting

    TBD: Convert prognostics models to use actual times
    """

    ahead_time: float = Field(gt=0)
    """How much time to forecast ahead (units: timesteps)"""
    resolution: float = Field(1, gt=0)
    """Resolution at which to produce forecasts (units: timesteps)"""
