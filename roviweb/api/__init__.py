"""Define the web application"""
from pathlib import Path
import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.templating import Jinja2Templates

from . import db, online

logger = logging.getLogger(__name__)

# Start the RestAPI connect
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"]
)
app.include_router(db.router)
app.include_router(online.router)

templates = Jinja2Templates(directory=Path(__file__).parent / "templates")

@app.get("/")
async def home(request: Request):
    return templates.TemplateResponse(
        request=request, name="home.html"
    )
