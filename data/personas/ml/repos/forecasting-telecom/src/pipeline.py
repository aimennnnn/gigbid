import prophet
import lightgbm


def run(frame):
    """Predict how much stock we need each week."""
    prepared = lightgbm.prepare(frame)
    return prophet.fit_predict(prepared)
