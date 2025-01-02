"""Utility operations for working with the DuckDB"""
import re

from duckdb import DuckDBPyConnection

import numpy as np

_data_types_to_sql = {
    'f': 'FLOAT',
    'i': 'INTEGER'
}
_name_re = re.compile('\w+$')


def register_data_source(conn: DuckDBPyConnection, name: str, first_record: dict[str, int | float | str]):
    """Create a new table in the database

    Args:
        conn: Connection to DuckDB
        name: Name used for the table
        first_record: First record for the database
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
