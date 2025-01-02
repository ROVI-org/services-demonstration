"""Define the web application"""
import logging

from fastapi import FastAPI
from fastapi.websockets import WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"]
)

logger = logging.getLogger('app')


@app.websocket('/upload')
async def upload_data(socket: WebSocket):
    """Open a socket connection for writing data to the database

    The first message into the websocket is a JSON document including the name of the dataset to write to.

    .. code-block: json

        "name": "module-1"

    The websocket will respond if it is ready to receive data and then continue without replying to the user.

    .. code-block: json

       {"success": true, "message": "Preparing to receive for dataset: module-1"}

    The subsequent messages are the data to be stored.
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
        name = msg['name']
        await socket.send_json({'success': True, 'message': f'Preparing to receive for dataset: {name}'})

    except WebSocketDisconnect:
        logger.info(f'Disconnected from client at {socket.client.host}')
