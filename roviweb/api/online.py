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
                           valid_time: float = 0.,
                           files: list[UploadFile] = ()) -> str:
    """Register an online estimator to be used for a specific data source

    Args:
        name: Name of the data source
        definition: Contents of a Python file which builds the model
        valid_time: Time at which the state of the estimator is valid
        files: Any files associated with the data
    """

    # Write the files to a temporary directory
    with TemporaryDirectory() as td:
        td = Path(td)
        for file in files:
            with open(td / file.filename, 'wb') as fo:
                shutil.copyfileobj(file.file, fo)

        # Execute the function to create the estimator
        estimator = load_variable(definition, working_dir=td)

        # Add it to the estimator collection
        register_estimator(name, EstimatorHolder(estimator=estimator, last_time=valid_time))

    return estimator.__class__.__name__


@router.get('/online/status')
async def status_estimator() -> dict[str, EstimatorStatus]:
    """Get the states of each estimator being evaluated"""

    output = {}
    for name, holder in list_estimators().items():
        names = holder.estimator.state_names
        estimated_state = holder.estimator.state

        output[name] = EstimatorStatus(
            state_names=list(names),
            latest_time=holder.last_time,
            mean=estimated_state.get_mean().tolist(),
            covariance=estimated_state.get_covariance().tolist(),
        )
    return output
