"""Endpoints related to state estimation"""
import numpy as np
import shutil
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Annotated

from fastapi import Form, UploadFile, APIRouter

from roviweb.online import EstimatorHolder, list_estimators, register_estimator
from roviweb.utils import load_variable
from roviweb.schemas import EstimatorStatus

router = APIRouter()


@router.post('/online/register')
async def upload_estimator(name: Annotated[str, Form()],
                           definition: Annotated[str, Form()],
                           required_time: float = 0.,
                           files: list[UploadFile] = ()) -> str:
    """Register an online estimator to be used for a specific data source

    Args:
        name: Name of the data source
        definition: Contents of a Python file which builds the model
        required_time: Amount of time required until we can train the estimator
        files: Any files associated with the data
    """

    # Write the files to a temporary directory
    with TemporaryDirectory() as td:
        td = Path(td)
        for file in files:
            with open(td / file.filename, 'wb') as fo:
                shutil.copyfileobj(file.file, fo)

        # Execute the function to create the estimator
        estimator_maker, offline_estimator = load_variable(
            definition,
            variable_name=('make_estimator', 'perform_offline_estimation'),
            working_dir=td)

        # Add it to the estimator collection
        holder = EstimatorHolder(
            estimator_builder=estimator_maker,
            offline_estimator=offline_estimator,
            start_time=required_time,
            last_time=-np.inf
        )

        # Make the estimator if no data are required
        if required_time <= 0:
            asoh, state = holder.offline_estimator(None)
            holder.estimator = holder.estimator_builder(asoh, state)
        register_estimator(name, holder)

    return str(holder)


@router.get('/online/status')
async def status_estimator() -> dict[str, EstimatorStatus]:
    """Get the states of each estimator being evaluated"""

    output = {}
    for name, holder in list_estimators().items():
        if holder.estimator is None:
            output[name] = EstimatorStatus(is_ready=False)

        names = holder.estimator.state_names
        estimated_state = holder.estimator.state

        output[name] = EstimatorStatus(
            is_ready=True,
            state_names=list(names),
            latest_time=holder.last_time,
            mean=estimated_state.get_mean().tolist(),
            covariance=estimated_state.get_covariance().tolist(),
        )
    return output
