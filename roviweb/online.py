"""Functions for managing online estimation"""
import dataclasses

from moirae.interface import row_to_inputs
from moirae.estimators.online import OnlineEstimator
from moirae.models.base import InputQuantities

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
