import ssis
import dax


def run(frame):
    """Track deliveries and stock in one report."""
    prepared = dax.prepare(frame)
    return ssis.fit_predict(prepared)
