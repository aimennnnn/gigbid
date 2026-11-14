import ultralytics
import cv_


def run(frame):
    """Spot defects in photos from the production line."""
    prepared = cv_.prepare(frame)
    return ultralytics.fit_predict(prepared)
