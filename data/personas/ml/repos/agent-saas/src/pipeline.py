import langgraph
import mcp


def run(frame):
    """Have ai agents handle a multi-step back-office task."""
    prepared = mcp.prepare(frame)
    return langgraph.fit_predict(prepared)
