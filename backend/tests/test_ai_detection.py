import numpy as np
import pytest
from pathlib import Path
from app.ai.detector import YOLOv8Detector, DetectedObject, DetectionResult, get_detector
from app.services.video_analyzer import MotionObservation, scan_video_motion


def test_yolov8_detector_initialization_and_inference():
    detector = get_detector()
    assert detector.is_ready is True

    # Test inference on a blank synthetic image
    frame = np.full((360, 480, 3), 100, dtype=np.uint8)
    result = detector.detect(frame, conf_threshold=0.30)
    assert isinstance(result, DetectionResult)
    assert isinstance(result.objects, tuple)
    assert result.annotated_frame is not None
    assert result.annotated_frame.shape == frame.shape


def test_yolov8_letterbox_geometry():
    detector = get_detector()
    frame = np.zeros((300, 600, 3), dtype=np.uint8)
    padded, ratio, (dw, dh) = detector._letterbox(frame, target_size=640)
    assert padded.shape == (640, 640, 3)
    assert ratio > 0
    assert dw >= 0
    assert dh >= 0


def test_motion_observation_ai_fields():
    obs = MotionObservation(
        timestamp_seconds=2.5,
        foreground_ratio=0.15,
        primary_label="person",
        is_semantic=True,
        detected_objects=(
            {"label": "person", "confidence": 0.88, "box": {"x": 10, "y": 20, "width": 50, "height": 100}},
        ),
    )
    assert obs.is_semantic is True
    assert obs.primary_label == "person"
    assert len(obs.detected_objects) == 1
    assert obs.detected_objects[0]["confidence"] == 0.88


def test_scan_video_motion_graceful_on_synthetic_video(tmp_path):
    # Create a small synthetic video with simple geometric motion
    import cv2
    video_path = tmp_path / "test_motion.avi"
    fourcc = cv2.VideoWriter_fourcc(*"MJPG")
    out = cv2.VideoWriter(str(video_path), fourcc, 10.0, (160, 120))
    for i in range(25):
        frame = np.zeros((120, 160, 3), dtype=np.uint8)
        # moving bright square
        cv2.rectangle(frame, (i * 4, 30), (i * 4 + 30, 70), (255, 255, 255), -1)
        out.write(frame)
    out.release()

    obs = list(scan_video_motion(video_path, frame_stride=2, threshold=0.03, min_gap_seconds=0.1, enable_ai=True))
    assert len(obs) > 0
    # Synthetic square is not a COCO object, so is_semantic should be False
    assert obs[0].is_semantic is False
    assert obs[0].snapshot_bytes is not None
