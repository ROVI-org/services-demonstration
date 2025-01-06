"""Command line utility for interacting with the web service"""
from argparse import ArgumentParser
from pathlib import Path

import msgpack
from battdat.data import BatteryDataset
from pydantic import TypeAdapter
from httpx_ws import connect_ws
import httpx

from roviweb.schemas import EstimatorStatus, TableStats


def upload_estimator(args):
    pointers = []  # Holds pointers to files being sent
    try:
        # Open pointers to all files
        context_files = []
        for file in args.context_file:
            file = Path(file)
            fp = open(file, 'rb')
            pointers.append(fp)
            context_files.append(('files', (file.name, fp)))

        # Read the in the estimator file
        estimator = Path(args.py_file).read_text()

        # Push to the web service
        reply = httpx.post(f'{args.url}/online/register',
                           data={'name': args.name, 'definition': estimator},
                           files=context_files)
        if reply.status_code != 200:
            raise ValueError(f'Upload failed status_code={reply.status_code}. {reply.text}')
        response = reply.json()
        print(f'Received a {response} for data_source={args.name}')
    finally:
        for pt in pointers:
            pt.close()


def get_status(args):
    # Pull database status from the web service
    response = httpx.get(f'{args.url}/dbstats')
    if response.status_code != 200:
        raise ValueError(f'Failed with status_code={response.status_code}. {response.text}')

    # Print the results
    result: dict[str, TableStats] = TypeAdapter(dict[str, TableStats]).validate_python(response.json())
    if len(result) == 0:
        print('No databases available')
    else:
        print('Database sizes:')
        for name, info in result.items():
            print(f'  {name}: {info.rows}')

    # Query the available estimators
    response = httpx.get(f'{args.url}/online/status')
    if response.status_code != 200:
        raise ValueError(f'Failed with status_code={response.status_code}. {response.text}')

    # Print the estimators
    result: dict[str, EstimatorStatus] = TypeAdapter(dict[str, EstimatorStatus]).validate_python(response.json())
    for name, info in result.items():
        print(f'Estimator for {name}:')
        print(f'  Latest time: {info.latest_time:.2f} s')


def upload_data(args):
    with connect_ws(f'{args.url}/upload') as ws:
        # Initialize connection
        ws.send_json({'name': args.name})
        msg = ws.receive_json()
        if not msg['success']:
            raise ValueError(f'Failed to start upload: {msg["reason"]}')

        # Start sending data
        dataset = BatteryDataset.from_hdf(args.path)
        for i, row in dataset.tables['raw_data'].iterrows():
            if args.max_to_upload is not None and i >= args.max_to_upload:
                break
            ws.send_bytes(msgpack.dumps(row.to_dict()))


def main(args=None):
    """Main entry point"""

    # Make the argument parser with one subparser for each action
    parser = ArgumentParser()
    parser.add_argument('--url', default='http://127.0.0.1', help='URL for the web service')
    subparsers = parser.add_subparsers(dest='action')

    subparser = subparsers.add_parser('status', help='Get application status')
    subparser.set_defaults(action=get_status)

    subparser = subparsers.add_parser('register', help='Register a state estimator')
    subparser.add_argument('name', help='Name of the data source associated with this estimator')
    subparser.add_argument('py_file', help='Path to the python file containing estimator definition')
    subparser.add_argument('context_file', nargs='*', help='Paths to additional files needed for estimator definition')
    subparser.add_argument('--valid-time', default=0., type=float, help='Test time at which estimator is valid')
    subparser.set_defaults(action=upload_estimator)

    subparser = subparsers.add_parser('upload', help='Upload data from a battdat HDF5 file')
    subparser.add_argument('--max-to-upload', help='Maximum number of rows to upload', default=None, type=int)
    subparser.add_argument('name', help='Name of the data source to create')
    subparser.add_argument('path', help='Path to the HDF5 file')
    subparser.set_defaults(action=upload_data)

    args = parser.parse_args(args)

    # Invoke the appropriate action
    if args.action is not None:
        args.action(args)
    else:
        raise ValueError(f'No action associated with {args.dest}')
