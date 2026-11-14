import looker_studio
import gspread


def run(frame):
    """Simple shareable reports for our clients."""
    prepared = gspread.prepare(frame)
    return looker_studio.fit_predict(prepared)
