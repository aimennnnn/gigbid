import lookml
import sql


def run(frame):
    """Agree what we measure and how."""
    prepared = sql.prepare(frame)
    return lookml.fit_predict(prepared)
