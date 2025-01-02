"""Utility operations for working with the DuckDB"""
import re
from typing import Dict

from duckdb import DuckDBPyConnection

import numpy as np

_data_types_to_sql = {
    'f': 'FLOAT',
    'i': 'INTEGER'
}
_name_re = re.compile(r'\w+$')

RecordType = dict[str, int | float | str]


def register_data_source(conn: DuckDBPyConnection, name: str, first_record: RecordType) -> Dict[str, str]:
    """Create a new table in the database

    Args:
        conn: Connection to DuckDB
        name: Name used for the table
        first_record: First record for the database
    Returns:
        Map of column names to SQL types
    """

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


def write_record(conn: DuckDBPyConnection, name: str, type_map: Dict[str, str], record: RecordType):
    """Write a series of records to a certain table

    Args:
        conn: Connection to DuckDB
        name: Name used for the table
        type_map: Map of column name to expected type
        record: Record to be written
    """

    conn.execute(
        f'INSERT INTO {name} ({", ".join(record.keys())}) VALUES ({", ".join("?" * len(record))})',
        [v if not type_map[k] == "VARCHAR" else str(v) for k, v in record.items()]
    )
