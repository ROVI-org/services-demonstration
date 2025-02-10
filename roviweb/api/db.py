"""API functions related to using the database"""
from datetime import datetime
from typing import Dict
import logging

import msgpack
from fastapi import APIRouter
from starlette.websockets import WebSocket, WebSocketDisconnect

from . import state
from roviweb.db import register_data_source, write_record, connect
from roviweb.schemas import TableStats

logger = logging.getLogger(__name__)
router = APIRouter()


@router.websocket('/db/upload/{name}')
async def upload_data(name: str, socket: WebSocket):
    """Open a socket connection for writing data to the database

    Messages are the data to be stored in `msgpack <https://pypi.org/project/msgpack/>`_ format.
    The web service will add a timestamp and then store the data as-is.

    Args:
        name: Name of the dataset
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
        type_map = register_data_source(name, record)

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
                    state_db_map = register_data_source(db_name, state_record)
                    state_db_ready = True
                write_record(db_name, state_db_map, state_record)

            # Write to database
            write_record(name, type_map, record)

            # Get next step
            msg = await socket.receive_bytes()
            record = msgpack.unpackb(msg)
            record['received'] = datetime.now().timestamp()
    except WebSocketDisconnect:
        logger.info(f'Disconnected from client at {socket.client.host}')


@router.get('/db/stats')
def get_db_stats() -> Dict[str, TableStats]:
    """Retrieve information about what data are stored"""

    conn = connect()

    # Get the stats for each dataset
    output = {}
    for name in state.known_datasets:
        # Get size information
        rows = conn.execute(
            'SELECT estimated_size FROM duckdb_tables() WHERE table_name = ?', [name]
        ).fetchone()[0]

        # Get column information
        columns = conn.execute('SELECT * FROM duckdb_columns() WHERE table_name = ?', [name]).df()
        columns = dict(zip(columns['column_name'], columns['data_type']))
        output[name] = TableStats(rows=rows, columns=columns)

    return output
