"""API functions related to using the database"""
from datetime import datetime
from typing import Dict
import logging

import msgpack
from battdat.schemas import BatteryMetadata
from fastapi import APIRouter
from starlette.websockets import WebSocket, WebSocketDisconnect

from . import state
from roviweb.db import register_data_source, write_record, register_battery, list_batteries
from roviweb.schemas import BatteryStats

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post('/db/register')
def register_data(metadata: BatteryMetadata) -> str:
    """Supply the metadata for a battery to the web service

    Args:
        metadata: Metadata associated with the data sources

    Returns:
        The name of the source
    """
    return register_battery(metadata)


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
def get_db_stats() -> Dict[str, BatteryStats]:
    """List the battery datasets available

    Returns:
        A map of battery name to information about what we hold about it
    """

    return list_batteries()
