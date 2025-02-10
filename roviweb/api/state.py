"""Objects which represent the globally-accessible state of the application"""
from roviweb.online import EstimatorHolder

# Holding the dataset and estimator names
known_datasets = set()
estimators: dict[str, EstimatorHolder] = {}
