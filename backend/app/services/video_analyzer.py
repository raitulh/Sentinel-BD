from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

import cv2


@dataclass(frozen=True)
class MotionObservation:
    timestamp_seconds: float
    foreground_ratio: float
    snapshot_bytes: bytes | None = None
    boxes: tuple[dict, ...] = ()
    primary_label: str | None = None
    is_semantic: bool = False
    detected_objects: tuple[dict, ...] = ()


def scan_video_motion(
    path: str | Path,
    *,
    frame_stride: int = 5,
    threshold: float = 0.08,
    min_gap_seconds: float = 2.0,
    max_width: int = 640,
    max_duration_seconds: int = 3600,
    max_frames: int = 100000,
    extract_snapshots: bool = True,
    enable_ai: bool = True,
    ai_threshold: float = 0.35,
) -> Iterator[MotionObservation]:
    """Extract coarse frame-difference observations and optional edge AI object detections from a local video.

    This platform operates strictly as a sensor intelligence assistant with human review.
    Scores represent foreground-pixel motion ratios and detector confidences.
    """
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        cap.release()
        raise ValueError("Could not open uploaded video; format may be unsupported or file invalid")
    fps = cap.get(cv2.CAP_PROP_FPS)
    if not fps or fps <= 0 or fps > 1000:
        fps = 25.0
    reported_frames = cap.get(cv2.CAP_PROP_FRAME_COUNT)
    if reported_frames and reported_frames > 0:
        if reported_frames > max_frames:
            cap.release()
            raise ValueError(f"Video exceeds the configured frame limit ({max_frames})")
        if reported_frames / fps > max_duration_seconds:
            cap.release()
            raise ValueError(f"Video exceeds the configured duration limit ({max_duration_seconds} seconds)")
    subtractor = cv2.createBackgroundSubtractorMOG2(history=120, varThreshold=32, detectShadows=False)
    frame_index = 0
    last_emitted = -10_000.0
    emitted = 0
    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            if frame_index >= max_frames:
                raise ValueError(f"Video exceeds the configured frame limit ({max_frames})")
            if frame_index % max(1, frame_stride) != 0:
                frame_index += 1
                continue
            height, width = frame.shape[:2]
            if width > max_width:
                new_height = max(1, int(height * (max_width / width)))
                frame = cv2.resize(frame, (max_width, new_height), interpolation=cv2.INTER_AREA)
            mask = subtractor.apply(frame)
            # Ignore the first few sampled frames while the background model initializes.
            timestamp = frame_index / fps
            if frame_index >= max(1, frame_stride * 3):
                ratio = float(cv2.countNonZero(mask)) / float(mask.shape[0] * mask.shape[1])
                if ratio >= threshold and timestamp - last_emitted >= min_gap_seconds:
                    boxes_list = []
                    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
                    cleaned_mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
                    contours, _ = cv2.findContours(cleaned_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                    min_area = max(80.0, float(mask.shape[0] * mask.shape[1]) * 0.003)
                    for cnt in contours:
                        area = cv2.contourArea(cnt)
                        if area >= min_area:
                            bx, by, bw, bh = cv2.boundingRect(cnt)
                            boxes_list.append({"x": int(bx), "y": int(by), "width": int(bw), "height": int(bh), "area": round(float(area), 1)})

                    # Run AI object detection on the keyframe
                    primary_label = None
                    is_semantic = False
                    detected_objects_list: list[dict] = []

                    if enable_ai:
                        try:
                            from app.ai.detector import get_detector
                            detector = get_detector()
                            if detector.is_ready:
                                det_res = detector.detect(frame, conf_threshold=ai_threshold, annotate=False)
                                if det_res.objects:
                                    is_semantic = True
                                    primary_label = det_res.primary_label
                                    detected_objects_list = [
                                        {"label": obj.label, "confidence": obj.confidence, "box": obj.box}
                                        for obj in det_res.objects
                                    ]
                        except Exception:
                            pass

                    snapshot_bytes = None
                    if extract_snapshots:
                        annotated = frame.copy()
                        if is_semantic and detected_objects_list:
                            # Draw tactical AI object bounding boxes
                            for obj in detected_objects_list:
                                obx = obj["box"]["x"]
                                oby = obj["box"]["y"]
                                obw = obj["box"]["width"]
                                obh = obj["box"]["height"]
                                lbl = str(obj["label"]).upper()
                                conf = int(obj["confidence"] * 100)
                                color = (68, 68, 239) if obj["label"] == "person" else (11, 158, 245) if any(v in obj["label"] for v in ["car", "truck", "bus", "motorcycle"]) else (129, 185, 16)
                                cv2.rectangle(annotated, (obx, oby), (obx + obw, oby + obh), color, 2)
                                badge_text = f"{lbl} {conf}%"
                                cv2.rectangle(annotated, (obx, max(0, oby - 18)), (min(annotated.shape[1], obx + len(badge_text) * 9), oby), (20, 20, 20), -1)
                                cv2.putText(annotated, badge_text, (obx + 2, max(12, oby - 5)), cv2.FONT_HERSHEY_SIMPLEX, 0.42, color, 1, cv2.LINE_AA)
                        else:
                            for b in boxes_list:
                                cv2.rectangle(annotated, (b["x"], b["y"]), (b["x"] + b["width"], b["y"] + b["height"]), (30, 215, 96), 2)
                                cv2.putText(annotated, f"MOTION {int(ratio * 100)}%", (b["x"], max(14, b["y"] - 6)), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (30, 215, 96), 1, cv2.LINE_AA)
                        ok_enc, enc = cv2.imencode(".jpg", annotated, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
                        if ok_enc:
                            snapshot_bytes = enc.tobytes()

                    final_boxes = tuple(
                        [o["box"] for o in detected_objects_list] if detected_objects_list else boxes_list
                    )
                    yield MotionObservation(
                        timestamp_seconds=round(timestamp, 3),
                        foreground_ratio=round(min(1.0, ratio), 4),
                        snapshot_bytes=snapshot_bytes,
                        boxes=final_boxes,
                        primary_label=primary_label,
                        is_semantic=is_semantic,
                        detected_objects=tuple(detected_objects_list),
                    )
                    last_emitted = timestamp
                    emitted += 1
                    if emitted >= 5000:
                        break
            frame_index += 1
    finally:
        cap.release()
