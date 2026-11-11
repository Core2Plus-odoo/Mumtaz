# On-device tracking files

MediaPipe Tasks Vision 1.2.2 (Apache License 2.0, Google LLC), vendored so the
kiosk try-on runs with no call to a CDN or any cloud service:

- `wasm/` — the vision runtime used by `@mediapipe/tasks-vision`
- `face_landmarker.task` — face landmarks (necklaces, pendants, sets, earrings)
- `hand_landmarker.task` — hand landmarks (rings, bangles, bracelets)

Camera frames are processed in the browser and never leave the device.
