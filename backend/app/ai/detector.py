from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

import cv2
import numpy as np

logger = logging.getLogger(__name__)

COCO_CLASSES: list[str] = [
    "person", "bicycle", "car", "motorcycle", "airplane", "bus", "train", "truck", "boat",
    "traffic light", "fire hydrant", "stop sign", "parking meter", "bench", "bird", "cat",
    "dog", "horse", "sheep", "cow", "elephant", "bear", "zebra", "giraffe", "backpack",
    "umbrella", "handbag", "tie", "suitcase", "frisbee", "skis", "snowboard", "sports ball",
    "kite", "baseball bat", "baseball glove", "skateboard", "surfboard", "tennis racket",
    "bottle", "wine glass", "cup", "fork", "knife", "spoon", "bowl", "banana", "apple",
    "sandwich", "orange", "broccoli", "carrot", "hot dog", "pizza", "donut", "cake", "chair",
    "couch", "potted plant", "bed", "dining table", "toilet", "tv", "laptop", "mouse",
    "remote", "keyboard", "cell phone", "microwave", "oven", "toaster", "sink",
    "refrigerator", "book", "clock", "vase", "scissors", "teddy bear", "hair drier", "toothbrush"
]

# Color palette in BGR for visual contrast
CLASS_COLORS_BGR: dict[str, tuple[int, int, int]] = {
    "person": (68, 68, 239),     # Red / Coral alert
    "car": (11, 158, 245),        # Amber / Orange
    "truck": (11, 158, 245),
    "bus": (11, 158, 245),
    "motorcycle": (11, 158, 245),
    "boat": (212, 182, 6),        # Cyan / Blue
    "airplane": (212, 182, 6),
}
DEFAULT_COLOR_BGR = (129, 185, 16)  # Tactical Emerald Green


@dataclass(frozen=True)
class DetectedObject:
    label: str
    confidence: float
    box: dict[str, int]  # {"x": int, "y": int, "width": int, "height": int}
    class_id: int


@dataclass(frozen=True)
class DetectionResult:
    objects: tuple[DetectedObject, ...]
    primary_label: str | None = None
    max_confidence: float = 0.0
    annotated_frame: np.ndarray | None = None


class YOLOv8Detector:
    """Local-first ONNX runtime detector for YOLOv8 architecture."""

    def __init__(self, model_path: str | Path | None = None) -> None:
        if model_path is None:
            # Default location: backend/app/ai/models/yolov8n.onnx
            model_path = Path(__file__).resolve().parent / "models" / "yolov8n.onnx"
        self.model_path = Path(model_path)
        self._session = None
        self._input_name: str | None = None
        self._input_shape: tuple[int, ...] | None = None
        self._is_ready: bool = False
        self._load_session()

    def _load_session(self) -> None:
        if not self.model_path.exists():
            logger.info("ONNX model file not found at %s. Detection will operate in fallback mode.", self.model_path)
            return

        try:
            import onnxruntime as ort
            # Configure local CPU session
            opts = ort.SessionOptions()
            opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
            opts.intra_op_num_threads = 2
            opts.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL

            self._session = ort.InferenceSession(
                str(self.model_path),
                sess_options=opts,
                providers=["CPUExecutionProvider"]
            )
            inputs = self._session.get_inputs()
            if inputs:
                self._input_name = inputs[0].name
                self._input_shape = tuple(inputs[0].shape)
            self._is_ready = True
            logger.info("YOLOv8 ONNX model loaded successfully from %s", self.model_path)
        except Exception as exc:
            logger.warning("Failed to initialize ONNX runtime session: %s", exc)
            self._session = None
            self._is_ready = False

    @property
    def is_ready(self) -> bool:
        return self._is_ready

    def _letterbox(
        self,
        img: np.ndarray,
        target_size: int = 640,
        pad_color: tuple[int, int, int] = (114, 114, 114)
    ) -> tuple[np.ndarray, float, tuple[float, float]]:
        """Resize and pad image while meeting target stride and maintaining aspect ratio."""
        orig_h, orig_w = img.shape[:2]
        r = min(target_size / orig_h, target_size / orig_w)
        new_unpad_w, new_unpad_h = int(round(orig_w * r)), int(round(orig_h * r))
        dw = (target_size - new_unpad_w) / 2
        dh = (target_size - new_unpad_h) / 2

        top, bottom = int(round(dh - 0.1)), int(round(dh + 0.1))
        left, right = int(round(dw - 0.1)), int(round(dw + 0.1))

        resized = cv2.resize(img, (new_unpad_w, new_unpad_h), interpolation=cv2.INTER_LINEAR)
        padded = cv2.copyMakeBorder(resized, top, bottom, left, right, cv2.BORDER_CONSTANT, value=pad_color)
        return padded, r, (dw, dh)

    def detect(
        self,
        frame: np.ndarray,
        *,
        conf_threshold: float = 0.35,
        nms_threshold: float = 0.45,
        annotate: bool = True,
        target_classes: Sequence[str] | None = None
    ) -> DetectionResult:
        """Run object detection on a BGR image frame."""
        if not self._is_ready or self._session is None or self._input_name is None:
            return DetectionResult(objects=(), primary_label=None, max_confidence=0.0, annotated_frame=frame.copy() if annotate else None)

        orig_h, orig_w = frame.shape[:2]
        # Preprocessing: letterbox -> RGB -> normalize 0-1 -> transpose NCHW
        padded_img, ratio, (dw, dh) = self._letterbox(frame, target_size=640)
        rgb_img = cv2.cvtColor(padded_img, cv2.COLOR_BGR2RGB)
        tensor = rgb_img.astype(np.float32) / 255.0
        tensor = np.transpose(tensor, (2, 0, 1))  # HWC to CHW
        tensor = np.expand_dims(tensor, axis=0)   # 1, 3, 640, 640

        # Inference
        try:
            outputs = self._session.run(None, {self._input_name: tensor})
        except Exception as exc:
            logger.warning("ONNX inference error: %s", exc)
            return DetectionResult(objects=(), primary_label=None, max_confidence=0.0, annotated_frame=frame.copy() if annotate else None)

        # Output shape is [1, 84, 8400]
        # Transpose to [8400, 84] -> 4 bbox coords + 80 class scores
        preds = np.squeeze(outputs[0]).T

        boxes_list: list[list[int]] = []
        confidences_list: list[float] = []
        class_ids_list: list[int] = []

        for row in preds:
            scores = row[4:]
            max_idx = int(np.argmax(scores))
            conf = float(scores[max_idx])
            if conf >= conf_threshold:
                label = COCO_CLASSES[max_idx] if max_idx < len(COCO_CLASSES) else f"class_{max_idx}"
                if target_classes is not None and label not in target_classes:
                    continue

                cx, cy, w, h = row[0:4]
                # Scale box back to original coordinates
                x1 = int(round((cx - w / 2.0 - dw) / ratio))
                y1 = int(round((cy - h / 2.0 - dh) / ratio))
                box_w = int(round(w / ratio))
                box_h = int(round(h / ratio))

                # Clamp to frame boundary
                x1 = max(0, min(orig_w - 1, x1))
                y1 = max(0, min(orig_h - 1, y1))
                box_w = max(1, min(orig_w - x1, box_w))
                box_h = max(1, min(orig_h - y1, box_h))

                boxes_list.append([x1, y1, box_w, box_h])
                confidences_list.append(conf)
                class_ids_list.append(max_idx)

        detected_objects: list[DetectedObject] = []
        annotated_frame = frame.copy() if annotate else None

        if boxes_list:
            indices = cv2.dnn.NMSBoxes(boxes_list, confidences_list, conf_threshold, nms_threshold)
            if len(indices) > 0:
                indices_flat = indices.flatten() if hasattr(indices, "flatten") else [int(i[0]) if isinstance(i, (list, tuple, np.ndarray)) else int(i) for i in indices]
                for idx in indices_flat:
                    c_id = class_ids_list[idx]
                    label = COCO_CLASSES[c_id] if c_id < len(COCO_CLASSES) else f"class_{c_id}"
                    conf = confidences_list[idx]
                    bx, by, bw, bh = boxes_list[idx]

                    obj = DetectedObject(
                        label=label,
                        confidence=round(conf, 4),
                        box={"x": bx, "y": by, "width": bw, "height": bh},
                        class_id=c_id
                    )
                    detected_objects.append(obj)

                    if annotated_frame is not None:
                        color = CLASS_COLORS_BGR.get(label, DEFAULT_COLOR_BGR)
                        # Tactical bounding box
                        cv2.rectangle(annotated_frame, (bx, by), (bx + bw, by + bh), color, 2)
                        
                        # Label badge
                        badge_text = f"{label.upper()} {int(conf * 100)}%"
                        font = cv2.FONT_HERSHEY_SIMPLEX
                        font_scale = 0.42
                        thickness = 1
                        (text_w, text_h), baseline = cv2.getTextSize(badge_text, font, font_scale, thickness)
                        
                        badge_y1 = max(0, by - text_h - 8)
                        badge_y2 = by
                        badge_x2 = min(orig_w, bx + text_w + 10)
                        
                        # Dark pill background
                        cv2.rectangle(annotated_frame, (bx, badge_y1), (badge_x2, badge_y2), (20, 20, 20), -1)
                        # Pill border
                        cv2.rectangle(annotated_frame, (bx, badge_y1), (badge_x2, badge_y2), color, 1)
                        # Text
                        cv2.putText(
                            annotated_frame,
                            badge_text,
                            (bx + 4, badge_y2 - 4),
                            font,
                            font_scale,
                            (255, 255, 255),
                            thickness,
                            cv2.LINE_AA
                        )

        primary_label = None
        max_conf = 0.0
        if detected_objects:
            # Sort by confidence descending
            detected_objects.sort(key=lambda o: o.confidence, reverse=True)
            primary_label = detected_objects[0].label
            max_conf = detected_objects[0].confidence

        return DetectionResult(
            objects=tuple(detected_objects),
            primary_label=primary_label,
            max_confidence=max_conf,
            annotated_frame=annotated_frame
        )


_GLOBAL_DETECTOR: YOLOv8Detector | None = None


def get_detector(model_path: str | Path | None = None) -> YOLOv8Detector:
    """Return singleton YOLOv8 detector instance."""
    global _GLOBAL_DETECTOR
    if _GLOBAL_DETECTOR is None:
        _GLOBAL_DETECTOR = YOLOv8Detector(model_path)
    return _GLOBAL_DETECTOR
