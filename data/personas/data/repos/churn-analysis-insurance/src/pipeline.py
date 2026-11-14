import lifelines
import pandas


def run(frame):
    """Explain why customers cancel."""
    prepared = pandas.prepare(frame)
    return lifelines.fit_predict(prepared)
