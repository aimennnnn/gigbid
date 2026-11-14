# object-detection-fintech

Internal tooling built for a fintech client. The goal was simple: spot defects in photos from the production line.

## Layout
- `src/` main pipeline
- `tests/` checks on the outputs
- `notebooks/` exploration, not used in production

## Notes
Outcome after rollout: detected 96% of defects at 30 frames per second on an edge device. Depends on `ultralytics` and `cv2`.
