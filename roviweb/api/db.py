"""API functions related to using the database"""
from datetime import datetime
from typing import Dict
import logging

import msgpack
from battdat.schemas import BatteryMetadata
from fastapi import APIRouter
from starlette.websockets import WebSocket, WebSocketDisconnect

from roviweb.db import register_data_source, write_one_record, register_battery, list_batteries, write_records
from roviweb.schemas import BatteryStats, RecordType
from ..online import update_estimator

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
async def stream_data(name: str, socket: WebSocket):
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
        while True:
            # Write to database
            write_one_record(name, type_map, record)

            # Update the estimator
            update_estimator(name)

            # Get next step
            msg = await socket.receive_bytes()
            record = msgpack.unpackb(msg)
            record['received'] = datetime.now().timestamp()
    except WebSocketDisconnect:
        logger.info(f'Disconnected from client at {socket.client.host}')


@router.post('/db/upload/{name}')
def upload_data(name: str, records: list[RecordType]) -> int:
    """Bulk upload data

    Args:
        name: Name of the dataset
        records: Records to be uploaded
    Returns:
        Number of records processed
    """

    if len(records) == 0:
        return 0

    # Register the data source then insert
    type_map = register_data_source(name, records[0])
    write_records(name, type_map, records)

    # Update the estimator
    update_estimator(name)
    return len(records)


@router.get('/db/stats')
def get_db_stats() -> Dict[str, BatteryStats]:
    """List the battery datasets available

    Returns:
        A map of battery name to information about what we hold about it
    """

    return list_batteries()
