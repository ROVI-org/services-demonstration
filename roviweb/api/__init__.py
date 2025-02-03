"""Define the web application"""
import logging
import shutil
from pathlib import Path
from datetime import datetime
from tempfile import TemporaryDirectory
from typing import Dict, Annotated

import msgpack
from fastapi import FastAPI, Form, UploadFile
from fastapi.websockets import WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from roviweb.db import register_data_source, write_record
from roviweb.online import load_estimator, EstimatorHolder
from roviweb.schemas import TableStats, EstimatorStatus
from . import state

logger = logging.getLogger(__name__)

# Start the RestAPI connect
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"]
)


@app.websocket('/db/upload/{name}')
async def upload_data(name: str, socket: WebSocket):
    """Open a socket connection for writing data to the database

    Messages are the data to be stored in `msgpack <https://pypi.org/project/msgpack/>`_ format.
    The web service will add a timestamp and then store the data as-is.

    Args:
        socket: The websocket created for this particular session
    """

    # Accept the connection
    await socket.accept()
    logger.info(f'Connected to client at {socket.client.host}')

    try:
        # Retrieve the name of the dataset
        state.known_datasets.add(name)
        logger.info(f'Ready to receive data for {name}')

        # Retrieve data
        msg = await socket.receive_bytes()
        record = msgpack.unpackb(msg)
        record['received'] = datetime.now().timestamp()
        type_map = register_data_source(state.conn, name, record)

        # Continue to write rows until disconnect
        #  TODO (wardlt): Batch writes
        state_db_ready = False
        while True:
            # Increment and store estimator
            if (holder := state.estimators.get(name)) is not None:
                holder.step(record)
                state_record = {'test_time': record['test_time']}
                for vname, val in zip(holder.estimator.state_names, holder.estimator.state.get_mean()):
                    state_record[vname.replace(".", "__").replace("[", "").replace("]", "")] = val

                db_name = f'{name}_estimates'
                if not state_db_ready:
                    state_db_map = register_data_source(state.conn, db_name, state_record)
                    state_db_ready = True
                write_record(state.conn, db_name, state_db_map, state_record)

            # Write to database
            write_record(state.conn, name, type_map, record)

            # Get next step
            msg = await socket.receive_bytes()
            record = msgpack.unpackb(msg)
            record['received'] = datetime.now().timestamp()
    except WebSocketDisconnect:
        logger.info(f'Disconnected from client at {socket.client.host}')


@app.get('/db/stats')
def get_db_stats() -> Dict[str, TableStats]:
    """Retrieve information about what data are stored"""

    # Get the stats for each dataset
    output = {}
    for name in state.known_datasets:
        # Get size information
        rows = state.conn.execute('SELECT estimated_size FROM duckdb_tables() WHERE table_name = ?', [name]).fetchone()[0]

        # Get column information
        columns = state.conn.execute('SELECT * FROM duckdb_columns() WHERE table_name = ?', [name]).df()
        columns = dict(zip(columns['column_name'], columns['data_type']))
        output[name] = TableStats(rows=rows, columns=columns)

    return output


@app.post('/online/register')
async def register_estimator(name: Annotated[str, Form()],
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
        estimator = load_estimator(definition, working_dir=td)

        # Add it to the estimator collection
        state.estimators[name] = EstimatorHolder(estimator=estimator, last_time=valid_time)

    return estimator.__class__.__name__


@app.get('/online/status')
async def status_estimator() -> dict[str, EstimatorStatus]:
    """Get the states of each estimator being evaluated"""

    output = {}
    for name, holder in state.estimators.items():
        names = holder.estimator.state_names
        estimated_state = holder.estimator.state

        output[name] = EstimatorStatus(
            state_names=list(names),
            latest_time=holder.last_time,
            mean=estimated_state.get_mean().tolist(),
            covariance=estimated_state.get_covariance().tolist(),
        )
    return output
