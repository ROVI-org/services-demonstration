"""Define the web application"""
from pathlib import Path
import logging

import numpy as np
import pandas as pd
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.templating import Jinja2Templates

from . import db, online, state

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

@app.get("/{name}")
async def status(request: Request, name: str):
    # Get the estimator status, if available
    table = None
    print(state.estimators)
    if name in state.estimators:
        est = state.estimators[name]
        est_state = est.estimator.state
        table = pd.DataFrame({
            'name': est.estimator.state_names,
            'value': est_state.get_mean(),
            'std': np.sqrt(np.diag(est_state.get_covariance()))
        })

    return templates.TemplateResponse(
        request=request, name="status.html", context={'name': name, 'table': table}
    )