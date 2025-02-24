# Using the Services Demo

The services demo is designed to run on a single computer.
Run it in a series of steps.

1. Start the web service
2. Register a online estimator
3. Register a forecaster
4. Stream data
5. Monitor progress

## Start Web Service

The application is a single service built with FastAPI. Launch it as a single process worker 

```commandline
uvicorn roviweb.api:app --reload --workers 1
```

> Note: A single worker process is _required_ because state is held in process memory.

There is no encryption or authentication. Launch the web service by opening the URL printed to screen in the uvicorn log (http://127.0.0.1:8000/).

Preview the API by opening http://127.0.0.1:8000/docs

## Register an Estimator

Online estimators adjust guesses for the health of a battery system at each as each new piece of data is acquired.
Supply an estimator by posting...

- The name of the associated system
- The test time at which the parameter estimates are valid
- A Python file which creates a [Moirae `OnlineEstimator`](https://rovi-org.github.io/auto-soh/estimators/index.html#online-estimators)

Register by calling a CLI tool which POSTs a request to the proper URL.

```commandline
rovicli diagnosis register module estimator.py initial-asoh.json
```

The registration process will create a callback that updates the estimator each
time data from the associated system is received.

## Register an Forecaster

Forecasts prognose the future health of a battery under a specific load profile.
As with the Estimators, register one by posting...

- The name of the associated system
- A Python file which creates a function that takes health history and load forecast, 
  and produces a future estimate.
- An SQL query for gathering data needed for forecast
- Any files needed to create the function (e.g., machine learning model weights)

Register by calling a CLI tool which POSTs a request to the proper URL.

```commandline
rovicli prognosis module forecaster.py "SELECT q_t__base_values FROM $TABLE_NAME$ ORDER BY test_time DESC LIMIT 10000" weights.pkl
```

## Stream Data

Stream data to the system from a [`battery-data-toolkit` HDF5 file](https://rovi-org.github.io/battery-data-toolkit/user-guide/formats.html#hdf5)
through a web socket.

Sending the dataset will create a new table in an SQL database. Columns will be defined by the first record sent to the database.

Use an API tool provided with this web service to upload.

```commandline
rovicli upload module module.h5
```

The CLI will first register metadata for the cell 
then send data points to the web service at a rate proportional to how they were initially collected.
For example, data originally acquired every minute will be sent to the web service every minute.
The  `--speedup` command line argument will shorten the interval between data points by a constant factor.

## Monitor Progress

The home page of the web service contains links to pages detailing the history and estimated health of each system.
