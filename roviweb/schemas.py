"""Data models for interacting with web service"""
from pydantic import BaseModel


class TableStats(BaseModel):
    rows: int
    """Number of rows in the database"""

    columns: dict[str, str]
    """Names and types of the columns"""
