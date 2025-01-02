"""Define the web application"""
import logging
from typing import Dict

import duckdb
import msgpack
from battdat.schemas import BatteryMetadata
from fastapi import FastAPI
from fastapi.websockets import WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from roviweb.db import register_data_source
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

known_datasets = set()


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
        data = msgpack.unpackb(msg)
        register_data_source(conn, name, data)
    except WebSocketDisconnect:
        logger.info(f'Disconnected from client at {socket.client.host}')


@app.get('/dbstats')
def get_db_stats() -> Dict[str, TableStats]:
    """Retrieve information about what data are stored"""

    # Get the stats for each dataset
    output = {}
    for name in known_datasets:
        stats = conn.execute('SELECT * FROM duckdb_columns() WHERE table_name = ?', [name]).df()
        columns = dict(zip(stats['column_name'], stats['data_type']))
        output[name] = TableStats(columns=columns)

    return output
