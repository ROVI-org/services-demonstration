"""Command line utility for interacting with the web service"""
import time
from argparse import ArgumentParser
from pathlib import Path

import msgpack
import numpy as np
import pandas as pd
from battdat.data import BatteryDataset
from pydantic import TypeAdapter
from httpx_ws import connect_ws
import httpx

from roviweb.schemas import EstimatorStatus, BatteryStats


def upload_function(args, functionality: str, **kwargs):
    """Upload a function to the web service

    Keyword args are added as arguments to the form data

    Args:
        args: Arguments passed to the CLI
        functionality: Name of the functionality
    """
    pointers = []  # Holds pointers to files being sent
    try:
        # Open pointers to all files
        context_files = []
        for file in args.context_file:
            file = Path(file)
            fp = open(file, 'rb')
            pointers.append(fp)
            context_files.append(('files', (file.name, fp)))

        # Read the in the definition file
        definition = Path(args.py_file).read_text()

        # Push to the web service
        reply = httpx.post(f'{args.url}/{functionality}/register',
                           data={'name': args.name, 'definition': definition, **kwargs},
                           files=context_files)
        if reply.status_code != 200:
            raise ValueError(f'Upload failed status_code={reply.status_code}. {reply.text}')
        response = reply.text
        print(f'Uploaded a {functionality} tool for data_source={args.name}. Response={response}')
    finally:
        for pt in pointers:
            pt.close()


def get_status(args):
    # Pull database status from the web service
    response = httpx.get(f'{args.url}/db/stats')
    if response.status_code != 200:
        raise ValueError(f'Failed with status_code={response.status_code}. {response.text}')

    # Print the results
    result: dict[str, BatteryStats] = TypeAdapter(dict[str, BatteryStats]).validate_python(response.json())
    if len(result) == 0:
        print('No batteries available')
    else:
        print('Database sizes:')
        for name, info in result.items():
            print(f'  {name}: {info.data_stats.rows if info.has_data else "No data"}')

    # Query the available estimators
    response = httpx.get(f'{args.url}/online/status')
    if response.status_code != 200:
        raise ValueError(f'Failed with status_code={response.status_code}. {response.text}')

    # Print the estimators
    result: dict[str, EstimatorStatus] = TypeAdapter(dict[str, EstimatorStatus]).validate_python(response.json())
    for name, info in result.items():
        print(f'Estimator for {name}:')
        print(f'  Latest time: {info.latest_time:.2f} s')


def print_status(args):
    # Pull status from the service
    est_status = httpx.get(f'{args.url}/online/status').json()
    if args.name not in est_status:
        return
    est_status = EstimatorStatus.model_validate(est_status[args.name])

    print(f'Estimator status at test_time: {est_status.latest_time:.1f} s:')
    state = pd.DataFrame({
        'name': est_status.state_names,
        'mean': est_status.mean,
        'std.': np.sqrt(np.diag(est_status.covariance))
    })
    print(state.to_string(index=False))


def stream_data(args):
    dataset = BatteryDataset.from_hdf(args.path)
    print(f'Beginning to stream data for {args.name}')

    with connect_ws(f'{args.url}/db/upload/{args.name}') as ws:
        # Start sending data
        last_time = None
        for i, row in dataset.tables['raw_data'].iterrows():
            # Pause to simulate data being acquired at known rates
            if args.clock_factor is not None and last_time is not None:
                sleep_time = (row['test_time'] - last_time) / args.clock_factor
                time.sleep(sleep_time)
            last_time = row['test_time']

            # Send a row
            if args.max_to_upload is not None and i >= args.max_to_upload:
                break
            ws.send_bytes(msgpack.dumps(row.to_dict()))

            # Print estimator status if we hit a marker
            if args.report_freq is not None and int(str(i)) % args.report_freq == 0:
                print_status(args)


def upload_data(args):
    # Load the data to be uploaded
    dataset = BatteryDataset.from_hdf(args.path)
    to_upload = dataset.tables['raw_data']
    if args.max_to_upload is not None:
        to_upload = to_upload.head(args.max_to_upload)

    # Send it in chunks based on the report freq
    num_chunks = len(to_upload) // args.report_freq + 1
    for chunk in np.array_split(to_upload, num_chunks):
        reply = httpx.post(f'{args.url}/db/upload/{args.name}', data=chunk.to_json(orient='records'))
        if reply.json() != len(chunk):
            raise ValueError(f'Upload failed: {reply.text}')
        print_status(args)


def register_metadata(args):
    """Upload the metadata"""
    metadata = BatteryDataset.get_metadata_from_hdf5(args.path)
    result = httpx.post(f'{args.url}/db/register', content=metadata.model_dump_json())
    print(result.json())


def main(args=None):
    """Main entry point"""

    # Make the argument parser with one subparser for each action
    parser = ArgumentParser()
    parser.add_argument('--url', default='http://127.0.0.1:8000', help='URL for the web service')
    subparsers = parser.add_subparsers(dest='action')

    subparser = subparsers.add_parser('status', help='Get application status')
    subparser.set_defaults(action=get_status)

    # Actions associated with diagnosis
    diag_subparser = subparsers.add_parser('diagnosis', help='Functions associated with diagnosing battery health')
    diag_subparsers = diag_subparser.add_subparsers(dest='action')

    subparser = diag_subparsers.add_parser('register', help='Register a state estimator')
    subparser.add_argument('name', help='Name of the data source associated with this estimator')
    subparser.add_argument('py_file', help='Path to the python file containing estimator definition')
    subparser.add_argument('context_file', nargs='*', help='Paths to additional files needed for estimator definition')
    subparser.add_argument('--valid-time', default=0., type=float, help='Test time at which estimator is valid')
    subparser.set_defaults(action=lambda x: upload_function(x, 'online'))

    # Actions associated with prognosis
    prog_subparser = subparsers.add_parser('prognosis', help='Functions for forecasting battery health')
    prog_subparsers = prog_subparser.add_subparsers(dest='action')

    subparser = prog_subparsers.add_parser('register', help='Register a health forecaster')
    subparser.add_argument('name', help='Name of the data source associated with this estimator')
    subparser.add_argument('py_file', help='Path to the python file containing forecast function definition')
    subparser.add_argument('sql_query', help='Query used to get history used for prognosis')
    subparser.add_argument('context_file', nargs='*', help='Paths to additional files needed for forecaster')
    subparser.set_defaults(action=lambda x: upload_function(x, 'prognosis', sql_query=x.sql_query))

    # Actions associated with metadata
    subparser = subparsers.add_parser('register', help='Register metadata for a cell')
    subparser.add_argument('path', help='Path to the H5 file holding the metadata')
    subparser.set_defaults(action=register_metadata)

    # Actions associated with data
    subparser = subparsers.add_parser('upload', help='Upload data from a battdat HDF5 file')
    subparser.add_argument('--max-to-upload', help='Maximum number of rows to upload',
                           default=None, type=int)
    subparser.add_argument('--report-freq', help='After how many data uploads to print estimator state',
                           default=None, type=int)
    subparser.add_argument('--clock-factor',
                           help='How much to accelerate uploading compared to rate data were collected.'
                                ' Uploads as fast as possible as the default', default=None, type=float)
    subparser.add_argument('name', help='Name of the data source to create')
    subparser.add_argument('path', help='Path to the HDF5 file')
    subparser.set_defaults(action=lambda x: upload_data(x) if x.clock_factor is None else stream_data(x))

    args = parser.parse_args(args)

    # Invoke the appropriate action
    if args.action is not None:
        args.action(args)
    else:
        raise ValueError(f'No action associated with {args.dest}')
