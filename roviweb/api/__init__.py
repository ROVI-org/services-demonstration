"""Define the web application"""
from typing import Annotated
from pathlib import Path
from io import StringIO
import logging

import numpy as np
import pandas as pd
import matplotlib as mpl
from matplotlib import pyplot as plt
from fastapi import FastAPI, Request, HTTPException, Response, Query
from fastapi.middleware.cors import CORSMiddleware
from starlette.templating import Jinja2Templates

from . import db, online, prognosis
from ..db import connect, list_batteries
from ..online import list_estimators
from roviweb.prognosis import perform_prognosis, make_load_scenario
from roviweb.schemas import LoadSpecification

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
app.include_router(prognosis.router)

templates = Jinja2Templates(directory=Path(__file__).parent / "templates")


@app.get("/")
async def home(request: Request):
    return templates.TemplateResponse(
        request=request, name="home.html", context=dict(datasets=list_batteries())
    )


@app.get("/dashboard/{name}")
async def dashboard(request: Request, name: str):
    # Raise 404 if no such dataset
    if name not in list_batteries():
        raise HTTPException(status_code=404, detail=f"No such dataset: {name}")

    # Get the estimator status, if available
    table = None
    if (est := list_estimators().get(name)) is not None:
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


@app.get("/dashboard/{name}/img/forecast.svg")
async def render_forecast(name, load: Annotated[LoadSpecification, Query()]):
    # Raise 404 if no such dataset
    if name not in list_batteries():  # TODO: Make faster by just checking dataset
        raise HTTPException(status_code=404, detail=f"No such dataset: {name}")
    if name not in list_estimators():
        raise HTTPException(status_code=404, detail=f"No health estimator for: {name}")
    conn = connect()

    # Get the entire history of the health estimates
    asoh_est = conn.execute(f'SELECT * FROM {name}_estimates').df()

    # Get the prognosis
    forecast = None
    try:
        load_scn = make_load_scenario(load)
        forecast = perform_prognosis(name, load_scn)
        forecast = forecast.join(load_scn.drop(columns=['test_time']))
        forecast['test_time'] += asoh_est['test_time'].max()
    except BaseException as e:
        print(f'Failed to make forecasts due to: {e}')

    # Make the figure
    n_asoh = len(asoh_est.columns) - 1
    fig, axs = plt.subplots(n_asoh // 2 + n_asoh % 2, 2, figsize=(6.5, 2 * n_asoh // 2), sharex=True, squeeze=False)
    try:

        for ax, col in zip(axs.flatten(), asoh_est.columns[1:]):
            ax.plot(asoh_est['test_time'] / 3600 / 24, asoh_est[col], color='blue')
            ax.set_title(col, fontsize=8, loc='left')

            if forecast is not None and col in forecast:
                ax.plot(forecast['test_time'] / 3600 / 24, forecast[col], color='red')

        for ax in axs[-1, :]:
            ax.set_xlabel('Time (d)')

        fig.tight_layout()
        io = StringIO()
        fig.savefig(io, format='svg', dpi=320)
        return Response(content=io.getvalue(), media_type='image/svg+xml')
    finally:
        plt.close(fig)
