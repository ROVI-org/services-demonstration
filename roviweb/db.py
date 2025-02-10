"""Utility operations for working with the DuckDB"""
import re
from uuid import uuid4
from typing import Dict
from functools import cache

from battdat.schemas import BatteryMetadata
from duckdb import DuckDBPyConnection
import duckdb

import numpy as np

_data_types_to_sql = {
    'f': 'FLOAT',
    'i': 'INTEGER'
}
_name_re = re.compile(r'\w+$')

RecordType = dict[str, int | float | str]


@cache  # Only connect once per session
def connect() -> DuckDBPyConnection:
    """Establish a connection to the data services"""
    return duckdb.connect(":memory:")  # For now, just memory. No persistence between runs


def register_battery(metadata: BatteryMetadata) -> str:
    """Register a battery by providing its metadata

    Args:
        metadata: Metadata of a battery system
    Returns:
        The name to be used for the source
    """

    # Insert the metadata as a JSON object
    name = metadata.name or uuid4()
    conn = connect()

    # Establish the database if the table does not exist
    conn.execute((
        'CREATE TABLE IF NOT EXISTS battery_metadata('
        'name VARCHAR PRIMARY KEY,'
        'metadata VARCHAR)'
    ))

    # Insert the data
    conn.execute(
        'INSERT INTO battery_metadata VALUES (?, ?)',
        [name, metadata.model_dump_json()]
    )
    return name


def register_data_source(name: str, first_record: RecordType) -> Dict[str, str]:
    """Create a new table in the database

    Args:
        name: Name used for the table
        first_record: First record for the database
    Returns:
        Map of column names to SQL types
    """
    conn = connect()

    # Determine the data types
    col_types = {}
    if not _name_re.match(name):
        raise ValueError(f'Database name ("{name}") contains bad characters.')
    for key, value in first_record.items():
        if not _name_re.match(key):
            raise ValueError(f'Column name ("{key}") contains bad characters!')
        col_types[key] = _data_types_to_sql.get(np.array(value).dtype.kind, 'VARCHAR')

    # Make the table
    col_section = ",\n   ".join(f'{k} {v}' for k, v in col_types.items())
    conn.execute(f'CREATE TABLE {name}( {col_section} );')
    return col_types


def write_record(name: str, type_map: Dict[str, str], record: RecordType):
    """Write a series of records to a certain table

    Args:
        name: Name used for the table
        type_map: Map of column name to expected type
        record: Record to be written
    """

    conn = connect()
    conn.execute(
        f'INSERT INTO {name} ({", ".join(record.keys())}) VALUES ({", ".join("?" * len(record))})',
        [v if not type_map[k] == "VARCHAR" else str(v) for k, v in record.items()]
    )
