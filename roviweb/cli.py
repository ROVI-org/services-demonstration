"""Command line utility for interacting with the web service"""
from argparse import ArgumentParser
from pathlib import Path

from pydantic import TypeAdapter
import httpx

from roviweb.schemas import EstimatorStatus


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
    result = response.json()
    if len(result) == 0:
        print('No databases available')

    # Query the available estimators
    response = httpx.get(f'{args.url}/online/status')
    if response.status_code != 200:
        raise ValueError(f'Failed with status_code={response.status_code}. {response.text}')

    # Print the estimators
    result: dict[str, EstimatorStatus] = TypeAdapter(dict[str, EstimatorStatus]).validate_python(response.json())
    for name, info in result.items():
        print(f'Estimator for {name}:')
        print(f'  Latest time: {info.latest_time:.2f} s')


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

    args = parser.parse_args(args)

    # Invoke the appropriate action
    if args.action is not None:
        args.action(args)
    else:
        raise ValueError(f'No action associated with {args.dest}')
