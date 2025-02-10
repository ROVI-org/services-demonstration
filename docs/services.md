# What do the "services" do?

ROVI will eventually use two different web services:

- A "Data Hub" which manages collecting and storing operational data
- A "Digital Twin" which allows engineers to access health models of each system.

The following sections detail the actions which we expected the web service to provide when building this demo.

## Metadata Upload

The `/db/register` endpoint receives metadata associated with a battery.
The inputs are a metadata document in the form specified by battery-data-toolkit.

## Data Upload

The `/db/upload/<name>` endpoint opens a web socket which receives a stream of operational data
for a specific battery.
Each message is a single timestamp of data packed in a compact, binary format via msgpack.

The web services creates a new SQL table based on the format of the first message.

Upon receipt of a message, the web services

1. Stores the data to the SQL table
2. Uses the record to update the state estimate

## DB Status Query

The `/db/stats` list which battery datasets are available.
The endpoint returns a record for each table describing:

- If metadata are available
- If data are available
- If an estimator is registered
- The number of rows
- The schema for the table

## Estimator Registration

The `/online/register` creates a tool to estimate battery health and associates it with a data source.
We use the Moirae package for online state estimation, which describes state estimators as Python objects.
As such, the endpoint requires the name of the data source and

- A Python script which creates the estimator as a variable named `estimator`
- Any files which must be in the same directory as the Python script

## Estimator Status

The `/online/status` endpoint prints the current estimates of battery health.
Each record contains at least:

- The latest time at which the health was estimated
- The names of every parameter being estimated
- The mean and covariance of a probability distribution for the parameters
