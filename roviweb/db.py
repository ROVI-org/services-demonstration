"""Utility operations for working with the DuckDB"""
import re
from uuid import uuid4
from typing import Dict
from functools import cache

from battdat.schemas import BatteryMetadata
from duckdb import DuckDBPyConnection
import duckdb

import numpy as np

from roviweb.schemas import TableStats, BatteryStats, RecordType
from roviweb.online import list_estimators

_data_types_to_sql = {
    'f': 'FLOAT',
    'i': 'INTEGER'
}
_name_re = re.compile(r'\w+$')


@cache  # Only connect once per session
def connect() -> DuckDBPyConnection:
    """Establish a connection to the data services"""
    conn = duckdb.connect(":memory:")  # For now, just memory. No persistence between runs

    # Establish the database if the table does not exist
    conn.execute((
        'CREATE TABLE IF NOT EXISTS battery_metadata('
        'name VARCHAR PRIMARY KEY,'
        'metadata VARCHAR)'
    ))
    return conn


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

    # Insert the data
    conn.execute(
        'INSERT OR REPLACE INTO battery_metadata VALUES (?, ?)',
        [name, metadata.model_dump_json()]
    )
    return name


def list_batteries() -> dict[str, TableStats]:
    """Retrieve information about what data are stored"""
    conn = connect()

    # List the cells in the metadata datable
    all_batteries = conn.sql('SELECT name FROM battery_metadata').fetchall()
    no_metadata = conn.sql('SELECT name FROM battery_metadata WHERE metadata IS NULL').fetchall()

    # Get the stats for each dataset
    output = {}
    estimators = list_estimators()
    for name, in all_batteries:
        # Get size information
        rows = conn.execute(
            'SELECT estimated_size FROM duckdb_tables() WHERE table_name = ?', [name]
        ).fetchone()
        if rows is not None:
            rows = rows[0]

            # Get column information
            columns = conn.execute('SELECT * FROM duckdb_columns() WHERE table_name = ?', [name]).df()
            columns = dict(zip(columns['column_name'], columns['data_type']))
            table_stats = TableStats(rows=rows, columns=columns)
        else:
            table_stats = None

        # Make the summary
        output[name] = BatteryStats(
            has_metadata=(name,) not in no_metadata,
            has_data=table_stats is not None,
            has_estimator=name in estimators,
            data_stats=table_stats
        )

    return output


def register_data_source(name: str, first_record: RecordType) -> Dict[str, str]:
    """Create a new table in the database

    Args:
        name: Name used for the table
        first_record: First record for the database
    Returns:
        Map of column names to SQL types
    """
    conn = connect()

    # Insert metadata into table if not present
    conn.execute('INSERT INTO battery_metadata VALUES (?, NULL) ON CONFLICT DO NOTHING;', [name])

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
