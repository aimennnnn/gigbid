import statsmodels
import openpyxl


def run(frame):
    """See where we are losing margin."""
    prepared = openpyxl.prepare(frame)
    return statsmodels.fit_predict(prepared)
