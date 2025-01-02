"""Data models for interacting with web service"""
from pydantic import BaseModel


class TableStats(BaseModel):
    columns: dict[str, str]
    """Names and types of the columns"""
