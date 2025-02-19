"""Methods used to forecast the performance of the battery in the future"""
import numpy as np
import pandas as pd

from roviweb.db import connect
from roviweb.schemas import ForecasterInfo

forecasters: dict[str, ForecasterInfo] = {}  # Just hold in memory now


# TODO (wardlt): Flesh this out
def make_load_scenario(ahead_time: float, resolution: float) -> pd.DataFrame:
    """Generate a load scenario according

    Args:
        ahead_time: How far into the future to predict
        resolution: Resolution of the time-series data
    """
    return pd.DataFrame({'time': np.arange(0, ahead_time, resolution)})


def perform_prognosis(name: str, load_scenario: pd.DataFrame) -> pd.DataFrame:
    """Execute a forecast for a certain cell into the future

    Args:
        name: Name of the cell to evaluate
        load_scenario: An anticipated load scenario (format TBD)
    Returns:
        Dataframe containing the values of the aSOH parameters for all points in the above formula
    """

    # Load the estimator then execute
    forecaster = forecasters[name]

    # Pull the required data
    query = forecaster.sql_query.replace('$TABLE_NAME$', f'{name}_estimates')
    input_data = connect().query(query).df()

    return forecaster.function(input_data, load_scenario)


def list_forecasters() -> dict[str, ForecasterInfo]:
    """List the estimators known to the web service

    Returns:
        Map of name to data structure holding it
    """
    return forecasters.copy()


def register_forecaster(name: str, estimator: ForecasterInfo):
    """Add a new estimators to those being tracked by the web service

    Args:
        name: Name of the associated dataset
        estimator: Estimator object
    """
    forecasters[name] = estimator
