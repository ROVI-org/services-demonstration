"""Define the web application"""
import logging
import shutil
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Dict, Annotated

import duckdb
import msgpack
from fastapi import FastAPI, Form, UploadFile
from fastapi.websockets import WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from roviweb.db import register_data_source, write_record
from roviweb.online import load_estimator, EstimatorHolder
from roviweb.schemas import TableStats

logger = logging.getLogger(__name__)

# Start the RestAPI connect
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"]
)

# Make a DuckDB database connection
conn = duckdb.connect(":memory:")  # For now, just memory. No persistence between runs

# Holding the dataset and estimator names
known_datasets = set()
estimators: dict[str, EstimatorHolder] = {}


@app.websocket('/upload')
async def upload_data(socket: WebSocket):
    """Open a socket connection for writing data to the database

    The first message into the websocket is a JSON document including the name of the dataset to write to.

    .. code-block: json

        {"name": "module_1"}

    The websocket will respond if it is ready to receive data and then continue without replying to the user.

    .. code-block: json

       {"success": true, "message": "Preparing to receive for dataset: module_1"}

    The subsequent messages are the data to be stored in `msgpack <https://pypi.org/project/msgpack/>`_ format.
    The web service will add a timestamp and then store the data as-is.

    Args:
        socket: The websocket created for this particular session
    """

    # Accept the connection
    await socket.accept()
    logger.info(f'Connected to client at {socket.client.host}')

    try:
        # Retrieve the name of the dataset
        msg = await socket.receive_json()
        if 'name' not in msg:
            await socket.send_json({'success': False, 'reason': 'Initial JSON message must contain a key "name"'})
            return
        name = msg['name']
        known_datasets.add(name)
        await socket.send_json({'success': True, 'message': f'Preparing to receive for dataset: {name}'})
        logger.info(f'Ready to receive data for {name}')

        # Retrieve data
        msg = await socket.receive_bytes()
        record = msgpack.unpackb(msg)
        type_map = register_data_source(conn, name, record)

        # Continue to write rows until disconnect
        #  TODO (wardlt): Batch writes
        while True:
            write_record(conn, name, type_map, record)
            msg = await socket.receive_bytes()
            record = msgpack.unpackb(msg)

    except WebSocketDisconnect:
        logger.info(f'Disconnected from client at {socket.client.host}')


@app.get('/dbstats')
def get_db_stats() -> Dict[str, TableStats]:
    """Retrieve information about what data are stored"""

    # Get the stats for each dataset
    output = {}
    for name in known_datasets:
        # Get size information
        rows = conn.execute('SELECT estimated_size FROM duckdb_tables() WHERE table_name = ?', [name]).fetchone()[0]

        # Get column information
        columns = conn.execute('SELECT * FROM duckdb_columns() WHERE table_name = ?', [name]).df()
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
        estimators[name] = EstimatorHolder(estimator=estimator, last_time=valid_time)

    return estimator.__class__.__name__
