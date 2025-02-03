"""Define the web application"""
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import state, db, online

logger = logging.getLogger(__name__)

# Start the RestAPI connect
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"]
)
app.include_router(db.router)
app.include_router(online.router)
