# Baldur Posture

Desk-worker posture monitoring from a local webcam. Recognition (this context) scores upright posture in real time; Warning and Oratory are separate concerns.

## Language

**Person**:
A single human detected in the camera frame and tracked for scoring.
_Avoid_: user, subject, target

**Pose keypoints**:
YOLO pose outputs per person (`xy`, `xyn`, `data` with visibility).
_Avoid_: landmarks, joints, skeleton

**Posture score**:
A 0-100 number from ear-shoulder verticality plus shoulder symmetry where higher means more upright.
_Avoid_: confidence, probability, health score

**Valid range**:
Scores at or above 70 are upright; recovery requires reaching 80 to stop flapping.
_Avoid_: threshold, good posture

**Dwell time**:
Continuous seconds outside valid range before emitting `bad_posture` (10s) or confirming `recovered` (3s).
_Avoid_: timeout, delay, window

**Recognition**:
The Python YOLO stage that captures movement and emits posture events. No UI.
_Avoid_: detection (too narrow), engine (implementation word)

**Warning**:
The deferred WPF stage that shows the fullscreen popup. Not part of this grill.
_Avoid_: alert, notification
