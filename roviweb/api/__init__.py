"""Define the web application"""
from pathlib import Path
from io import StringIO
import logging

import numpy as np
import pandas as pd
import matplotlib as mpl
from matplotlib import pyplot as plt
from fastapi import FastAPI, Request, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from starlette.templating import Jinja2Templates

from . import db, online, state
from ..db import connect, list_batteries

logger = logging.getLogger(__name__)
mpl.use('Agg')

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


@app.get("/dashboard/{name}")
async def dashboard(request: Request, name: str):
    # Raise 404 if no such dataset
    if name not in list_batteries():
        raise HTTPException(status_code=404, detail=f"No such dataset: {name}")

    # Get the estimator status, if available
    table = None
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


@app.get("/dashboard/{name}/img/history.svg")
async def render_history(name):
    # Raise 404 if no such dataset
    if name not in list_batteries():  # TODO: Make faster by just checking dataset
        raise HTTPException(status_code=404, detail=f"No such dataset: {name}")
    conn = connect()

    # Get the latest time in the database
    last_time, = conn.sql(f'SELECT MAX(test_time) from {name}').fetchone()
    data = conn.execute(f'SELECT test_time, voltage, current FROM {name} '
                        f'WHERE test_time > {last_time - 24 * 3600}').df()

    # Convert time to time since latest in hours
    data['since_pres'] = (data['test_time'] - last_time) / 3600.

    # Make the figure
    fig, axs = plt.subplots(2, 1, figsize=(3.5, 4.), sharex=True)
    try:

        axs[0].plot(data['since_pres'], data['voltage'])
        axs[0].set_ylabel('Voltage (V)')

        axs[1].plot(data['since_pres'], data['current'])
        axs[1].set_ylabel('Current (A)')
        axs[1].set_xlabel('Time (hr)')

        fig.tight_layout()
        io = StringIO()
        fig.savefig(io, format='svg', dpi=320)
        return Response(content=io.getvalue(), media_type='image/svg+xml')
    finally:
        plt.close(fig)
