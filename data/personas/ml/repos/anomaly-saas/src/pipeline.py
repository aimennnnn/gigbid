import sklearn
import kafka


def run(frame):
    """Warn us when a machine starts behaving oddly."""
    prepared = kafka.prepare(frame)
    return sklearn.fit_predict(prepared)
