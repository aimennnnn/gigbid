import scipy
import statsmodels


def run(frame):
    """Tell us whether the new checkout actually works better."""
    prepared = statsmodels.prepare(frame)
    return scipy.fit_predict(prepared)
