import google_analytics_data
import pandas


def run(frame):
    """Work out which ads actually bring sales."""
    prepared = pandas.prepare(frame)
    return google_analytics_data.fit_predict(prepared)
