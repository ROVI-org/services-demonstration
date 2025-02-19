import pickle

import numpy as np
import pandas as pd

from scipy.stats import skew, kurtosis
from scipy.signal import welch
from scipy.stats import entropy


def extract_features(series):
    """Compute features for a series of aSOH values"""
    diff = np.diff(series)
    psd = welch(series, nperseg=50)[1]

    return np.array([
        series.mean(), series.std(), series.min(), series.max(), series.median(),
        skew(series), kurtosis(series), diff.mean(), diff.std(),
        np.percentile(series, 25), np.percentile(series, 75),
        entropy(np.histogram(series, bins=10)[0] + 1),
        psd.mean(), psd.std()
    ])


def poly(x, params):
    return sum([params[i] * x ** i for i in range(len(params))])


# Load the preprocessor and model
forecast_model_path = 'camp_forecast_model.pkl'
pca_model_path = 'pca_model.pkl'
with open(pca_model_path, "rb") as f:
    pca = pickle.load(f)

with open(forecast_model_path, "rb") as f:
    forecast_model = pickle.load(f)


def forecast(input_df: pd.DataFrame, load_scenario: pd.DataFrame) -> pd.DataFrame:
    # Run inference to get the model inputs
    series = input_df['q_t__base_values']
    X = extract_features(series).reshape(1, -1)
    X_pca = pca.transform(series.to_numpy().reshape(1, -1))
    X_combined = np.hstack([X, X_pca])

    model_parameters = forecast_model.predict(X_combined)[0]
    model_parameters = model_parameters[1:round(model_parameters[0]) + 2]

    # Make the forecast given the input data frame and predicted outputs
    forecast_len = len(input_df) + len(load_scenario)
    x = np.linspace(0, forecast_len, forecast_len)
    forecast_vals = np.abs(poly(x, model_parameters))
    forecast_vals = pd.Series(forecast_vals)

    return pd.DataFrame({'q_t.base_values': forecast_vals[len(input_df):]})
