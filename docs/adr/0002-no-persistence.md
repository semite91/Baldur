# No persistence, memory-only scoring

We store no images, video, keypoints, or scores; scoring holds the current frame in memory and emits only `bad_posture`, `recovered`, `heartbeat`, and `error` JSON-lines. We chose this because continuous camera recording is a privacy liability, trading debuggability and analytics for user trust.

## Considered Options

- Persist keypoints/scores for calibration: rejected, violates the no-data promise in `project.md`.
