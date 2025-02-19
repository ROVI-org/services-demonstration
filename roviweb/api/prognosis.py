"""Endpoints related to registering and executing prognosis"""
from tempfile import TemporaryDirectory
from typing import Annotated
from pathlib import Path
import shutil

from fastapi import Form, UploadFile, APIRouter
from fastapi.params import Query

from roviweb.utils import load_variable
from roviweb.schemas import ForecasterInfo, LoadSpecification
from roviweb.prognosis import register_forecaster, make_load_scenario, perform_prognosis

router = APIRouter()


# TODO (wardlt): Split the query's parts into separate variables to reduce
#  freedom of users to inject horrible/destructive queries
@router.post('/prognosis/register')
async def upload_forecaster(
        name: Annotated[str, Form()],
        definition: Annotated[str, Form()],
        sql_query: Annotated[str, Form(pattern=r'SELECT[^;]+(?:from|FROM) \$TABLE_NAME\$')],
        files: list[UploadFile] = ()) -> str:
    """Register a prognosis tool to be used for a single data source

    Args:
        name: Name of the data source associated with this forecaster
        definition: Contents of a Python file which builds the forecaster
            The file must contain a function named "forecast" which will take a dataframe of input
            observations following the format specified from :attr:`sql_query` and
            a Dataframe of the load expectations
        sql_query: Query used against the time series database to gather inference inputs
        files: Any files associated with the forecaster
    Returns:
        Summary of the forecaster
    """

    # Write the files to a temporary directory
    with TemporaryDirectory() as td:
        td = Path(td)
        for file in files:
            with open(td / file.filename, 'wb') as fo:
                shutil.copyfileobj(file.file, fo)

        # Load the inference function
        function = load_variable(definition, variable_name='forecast', working_dir=td)

    # Register it
    forecaster = ForecasterInfo(function=function, sql_query=sql_query)
    register_forecaster(name, forecaster)

    return str(forecaster)


@router.get('/prognosis/{name}/run')
def run_prognosis(name: str, data: Annotated[LoadSpecification, Query()]) -> dict[str, list[float]]:
    """Run prognosis for a certain system under user-defined load conditions

    Args:
        name: Name of the system in question
        data: Load specification
    Returns:
        Data for the load forecast and aSOH changes
    """

    load = make_load_scenario(data)
    forecast = perform_prognosis(name, load)
    return {**load.to_dict(orient='list'), **forecast.to_dict(orient='list')}
