# On-device tracking files

MediaPipe Tasks Vision 1.2.2 (Apache License 2.0, Google LLC), vendored so the
kiosk try-on runs with no call to a CDN or any cloud service:

- `wasm/` — the vision runtime used by `@mediapipe/tasks-vision`
- `face_landmarker.task` — face landmarks (necklaces, pendants, sets, earrings)
- `hand_landmarker.task` — hand landmarks (rings, bangles, bracelets)
- `pose_landmarker_lite.task` — body landmarks (shoulders, hips, ankles) for the
  fit estimate: height from the shoulders or head-to-ankle, scaled by the iris

Camera frames are processed in the browser and never leave the device.
