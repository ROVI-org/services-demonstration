"""Functions for managing online estimation"""
import logging
import dataclasses
from battdat.data import BatteryDataset, CellDataset
from typing import Callable

from moirae.interface import row_to_inputs
from moirae.estimators.online import OnlineEstimator
from moirae.models.base import InputQuantities, HealthVariable, GeneralContainer

from roviweb.db import register_data_source, connect, write_records, get_metadata
from roviweb.schemas import RecordType

logger = logging.getLogger(__name__)


@dataclasses.dataclass
class EstimatorHolder:
    """Class which holds tools to build an estimator, the estimator, and data about its progress"""

    offline_estimator: Callable[[BatteryDataset | None], tuple[HealthVariable, GeneralContainer]]
    """Function which generates initial health and state estimates"""
    estimator_builder: Callable[[HealthVariable, GeneralContainer], OnlineEstimator]
    """Function which builds an estimator from initial health estimates"""
    start_time: float
    """Time at which enough data has been acquired to start estimation (units: s)"""
    last_time: float
    """Test time at which the states are estimated (units: s)"""
    estimator: OnlineEstimator | None = None
    """Estimator being propagated"""
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

    # Pull the estimator
    missing = name not in estimators
    if missing and not missing_ok:
        raise ValueError(f'No estimator associated with: {name}')
    elif missing:
        return None
    holder = estimators[name]

    # Build an estimator if none yet available
    if holder.estimator is None and not build_estimator(name, holder):
        return None

    # Update using the most recent data
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


def build_estimator(name: str, holder: EstimatorHolder) -> bool:
    """Build a new estimator given what data are available in the database

    Args:
        name: Name of the associated dataset
        holder: Toolset for building the estimator
    Returns:
        Whether the estimator was built
    """

    conn = connect()

    # Check whether enough data are available
    first_time, last_time = conn.execute(f'SELECT MIN(test_time),MAX(test_time) FROM {name}').fetchone()
    if last_time - first_time < holder.start_time:
        return False

    # Pull the data and metadata
    raw_data = conn.execute(f'SELECT * FROM {name} ORDER BY test_time ASC').df()
    metadata = get_metadata(name)
    dataset = CellDataset(raw_data=raw_data, metadata=metadata)

    # Run offline estimation to get initial parameter guesses
    init_asoh, init_state = holder.offline_estimator(dataset)
    holder.estimator = holder.estimator_builder(init_asoh, init_state)
    return True
