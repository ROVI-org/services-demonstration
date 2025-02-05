"""Objects which represent the globally-accessible state of the application"""
import duckdb

from roviweb.online import EstimatorHolder


# Make a DuckDB database connection
conn = duckdb.connect(":memory:")  # For now, just memory. No persistence between runs

# Holding the dataset and estimator names
known_datasets = set()
estimators: dict[str, EstimatorHolder] = {}
