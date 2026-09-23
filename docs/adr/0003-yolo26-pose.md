# YOLO26-pose with stable fallback

Recognition uses Ultralytics `yolo26n-pose.pt` (`model(source=0, stream=True)`, `result.keypoints.xy/xyn/data`), falling back to the latest stable `*-pose.pt` if v26 wheels fail on Windows. We chose this because pose keypoints are the only input to the posture score and the Ultralytics API is stable across pose variants, trading newest-model chasing for an installable baseline.

## Consequences

- Notebook header must pin `ultralytics`, `torch`, and `opencv-python` versions after the env spike.
