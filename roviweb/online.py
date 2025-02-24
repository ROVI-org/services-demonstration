"""Functions for managing online estimation"""
import dataclasses

from moirae.interface import row_to_inputs
from moirae.estimators.online import OnlineEstimator
from moirae.models.base import InputQuantities

from roviweb.db import register_data_source, connect, write_records
from roviweb.schemas import RecordType


@dataclasses.dataclass
class EstimatorHolder:
    """Class which holds the estimator and data about its progress"""

    estimator: OnlineEstimator
    """Estimator being propagated"""
    last_time: float
    """Test time at which the states are estimated"""
    _last_inputs: InputQuantities | None = None
    """Inputs from the last step"""

    def step(self, record: RecordType):
        """Step forward the estimator if possible"""

        # Do nothing if the records are before the estimator's timestep
        if record['test_time'] < self.last_time:
            return

        # Convert the record to inputs
        inputs, outputs = row_to_inputs(record)

        # Step if we have the previous step
        if self._last_inputs is not None:
            self.estimator.step(inputs, outputs)

        # Update state
        self._last_inputs = inputs
        self.last_time = record['test_time']


estimators: dict[str, EstimatorHolder] = {}  # Just hold in memory now


def list_estimators() -> dict[str, EstimatorHolder]:
    """List the estimators known to the web service

    Returns:
        Map of name to data structure holding it
    """
    return estimators.copy()


def register_estimator(name: str, estimator: EstimatorHolder):
    """Add a new estimators to those being tracked by the web service

    Args:
        name: Name of the associated dataset
        estimator: Estimator object
    """
    estimators[name] = estimator


def update_estimator(name: str, missing_ok: bool = True) -> EstimatorHolder | None:
    """Update an estimator with the latest data, record in DB

    Args:
        name: Name of the associated dataset
        missing_ok: Whether to error if there is no estimator available
    Returns:
        The latest copy of the estimator
    """

    # Crash if no such estimator
    missing = name not in estimators
    if missing and not missing_ok:
        raise ValueError(f'No estimator associated with: {name}')
    elif missing:
        return None

    # Update using the most recent data
    holder = estimators[name]
    conn = connect()
    new_data = conn.execute(f'SELECT * FROM {name} WHERE test_time >= $1 ORDER BY test_time ASC',
                            [holder.last_time]).df()
    new_records = []
    for _, record in new_data.iterrows():
        holder.step(record)
        holder.last_time = record['test_time']
        state_record = {'test_time': record['test_time']}
        for vname, val in zip(holder.estimator.state_names, holder.estimator.state.get_mean()):
            state_record[vname.replace(".", "__").replace("[", "").replace("]", "")] = val
        new_records.append(state_record)

    # Store the results in a database
    db_name = f'{name}_estimates'
    state_db_map = register_data_source(db_name, new_records[0])
    write_records(db_name, state_db_map, new_records)
