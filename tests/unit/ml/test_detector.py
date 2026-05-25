"""
Unit tests for YoloDetector helper methods.

YOLO model is never loaded — all tests patch `ml.detector.YOLO` at import time.
All tests use synthetic/fabricated data.
"""
import pytest
from unittest.mock import MagicMock, patch


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_mock_model(names: dict) -> MagicMock:
    """Build a minimal mock YOLO model with the given class-name mapping."""
    model = MagicMock()
    model.names = names
    return model


def make_mock_results(xyxy_list, cls_list, conf_list):
    """
    Build a mock YOLO results object compatible with _parse_detections.

    _parse_detections does:
        boxes = results[0].boxes
        for box, cls, conf in zip(boxes.xyxy, boxes.cls, boxes.conf):
            cls_i  = int(cls)
            conf_f = float(conf)
            x1,y1,x2,y2 = map(float, box)

    So:
        - boxes.xyxy  must be iterable; each element must be iterable with 4 floats
        - boxes.cls   must be iterable; each element must support int()
        - boxes.conf  must be iterable; each element must support float()
        - len(boxes)  must support truthiness (used in `if boxes is None or len(boxes) == 0`)
    """
    result = MagicMock()
    boxes = MagicMock()
    # Use plain Python lists of lists / floats — avoids torch dependency
    boxes.xyxy = [[float(v) for v in row] for row in xyxy_list]
    boxes.cls = [float(c) for c in cls_list]
    boxes.conf = [float(f) for f in conf_list]
    boxes.__len__ = lambda self: len(xyxy_list)
    result.boxes = boxes
    return [result]


# ---------------------------------------------------------------------------
# Fixture: a patched YoloDetector instance (never calls real YOLO constructor)
# ---------------------------------------------------------------------------

def _make_detector(model_names, min_conf=0.3, min_player_w=30, min_player_h=50):
    """Return a YoloDetector with a fake model and no real YOLO loading."""
    with patch("ml.detector.YOLO"):
        from ml.detector import YoloDetector
        det = YoloDetector.__new__(YoloDetector)
        det.model = make_mock_model(model_names)
        det.min_conf = min_conf
        det.min_player_w = min_player_w
        det.min_player_h = min_player_h
        return det


# ===========================================================================
# _discover_class_ids
# ===========================================================================

class TestDiscoverClassIds:
    def test_football_model_discovers_player_and_ball(self):
        """Model with 'player', 'goalkeeper', and 'ball' classes → correct IDs."""
        with patch("ml.detector.YOLO"):
            from ml.detector import YoloDetector
            det = YoloDetector.__new__(YoloDetector)
            det.model = make_mock_model({0: "player", 1: "goalkeeper", 2: "ball"})
            det.min_conf = 0.3
            det.min_player_w = 30
            det.min_player_h = 50
            player_ids, ball_id = det._discover_class_ids()

        assert 0 in player_ids   # "player"
        assert 1 in player_ids   # "goalkeeper"
        assert ball_id == 2

    def test_coco_model_falls_back_to_coco_constants(self):
        """Model with no player/ball keywords → fallback to COCO (0=person, 32=sports ball)."""
        with patch("ml.detector.YOLO"):
            from ml.detector import YoloDetector, COCO_PERSON_CLS, COCO_BALL_CLS
            det = YoloDetector.__new__(YoloDetector)
            det.model = make_mock_model({5: "car", 7: "truck"})
            det.min_conf = 0.3
            det.min_player_w = 30
            det.min_player_h = 50
            player_ids, ball_id = det._discover_class_ids()

        assert player_ids == list(COCO_PERSON_CLS)
        assert ball_id == COCO_BALL_CLS

    def test_model_with_only_player_keyword_no_ball(self):
        """Model has player class but no ball class → ball falls back to COCO."""
        with patch("ml.detector.YOLO"):
            from ml.detector import YoloDetector, COCO_BALL_CLS
            det = YoloDetector.__new__(YoloDetector)
            det.model = make_mock_model({0: "player", 1: "car"})
            det.min_conf = 0.3
            det.min_player_w = 30
            det.min_player_h = 50
            player_ids, ball_id = det._discover_class_ids()

        assert 0 in player_ids
        assert ball_id == COCO_BALL_CLS

    def test_model_with_only_ball_keyword_no_player(self):
        """Model has ball but no player class → player falls back to COCO."""
        with patch("ml.detector.YOLO"):
            from ml.detector import YoloDetector, COCO_PERSON_CLS
            det = YoloDetector.__new__(YoloDetector)
            det.model = make_mock_model({0: "ball", 1: "car"})
            det.min_conf = 0.3
            det.min_player_w = 30
            det.min_player_h = 50
            player_ids, ball_id = det._discover_class_ids()

        assert player_ids == list(COCO_PERSON_CLS)
        assert ball_id == 0

    def test_case_insensitive_keyword_matching(self):
        """Keyword matching should be case-insensitive (uses .lower())."""
        with patch("ml.detector.YOLO"):
            from ml.detector import YoloDetector
            det = YoloDetector.__new__(YoloDetector)
            det.model = make_mock_model({0: "PLAYER", 1: "Ball"})
            det.min_conf = 0.3
            det.min_player_w = 30
            det.min_player_h = 50
            player_ids, ball_id = det._discover_class_ids()

        assert 0 in player_ids
        assert ball_id == 1

    def test_empty_model_names_uses_all_fallbacks(self):
        """Model with no named classes → both player and ball fall back to COCO."""
        with patch("ml.detector.YOLO"):
            from ml.detector import YoloDetector, COCO_PERSON_CLS, COCO_BALL_CLS
            det = YoloDetector.__new__(YoloDetector)
            det.model = make_mock_model({})
            det.min_conf = 0.3
            det.min_player_w = 30
            det.min_player_h = 50
            player_ids, ball_id = det._discover_class_ids()

        assert player_ids == list(COCO_PERSON_CLS)
        assert ball_id == COCO_BALL_CLS


# ===========================================================================
# _parse_detections
# ===========================================================================

class TestParseDetections:
    def _make_det(self):
        """Returns a bare YoloDetector without calling __init__."""
        with patch("ml.detector.YOLO"):
            from ml.detector import YoloDetector
            det = YoloDetector.__new__(YoloDetector)
            det.min_conf = 0.5
            det.min_player_w = 30
            det.min_player_h = 50
            det.player_classes = [0]
            det.ball_class = 32
            return det

    def test_empty_boxes_returns_empty_lists(self):
        det = self._make_det()
        result = MagicMock()
        boxes = MagicMock()
        boxes.__len__ = lambda self: 0
        result.boxes = boxes
        detections, balls = det._parse_detections([result])
        assert detections == []
        assert balls == []

    def test_none_boxes_returns_empty_lists(self):
        det = self._make_det()
        result = MagicMock()
        result.boxes = None
        detections, balls = det._parse_detections([result])
        assert detections == []
        assert balls == []

    def test_low_confidence_player_discarded(self):
        """Detection below min_conf=0.5 is discarded."""
        det = self._make_det()
        results = make_mock_results(
            xyxy_list=[[0.0, 0.0, 50.0, 100.0]],
            cls_list=[0],
            conf_list=[0.2],  # < 0.5 → discarded
        )
        detections, balls = det._parse_detections(results)
        assert detections == []

    def test_small_bbox_player_discarded(self):
        """Player bbox smaller than min_player_w or min_player_h is discarded."""
        det = self._make_det()
        # w=10 < min_player_w=30
        results = make_mock_results(
            xyxy_list=[[0.0, 0.0, 10.0, 100.0]],
            cls_list=[0],
            conf_list=[0.9],
        )
        detections, balls = det._parse_detections(results)
        assert detections == []

    def test_small_height_player_discarded(self):
        """Player bbox with h < min_player_h is discarded."""
        det = self._make_det()
        # h=20 < min_player_h=50
        results = make_mock_results(
            xyxy_list=[[0.0, 0.0, 50.0, 20.0]],
            cls_list=[0],
            conf_list=[0.9],
        )
        detections, balls = det._parse_detections(results)
        assert detections == []

    def test_valid_player_detection_accepted(self):
        """Valid player (conf OK, size OK) goes to detections list."""
        det = self._make_det()
        results = make_mock_results(
            xyxy_list=[[0.0, 0.0, 50.0, 100.0]],
            cls_list=[0],
            conf_list=[0.9],
        )
        detections, balls = det._parse_detections(results)
        assert len(detections) == 1
        assert balls == []

    def test_valid_player_format_is_xywh_conf_cls(self):
        """Detection output format must be [[x1, y1, w, h], conf, cls_id]."""
        det = self._make_det()
        results = make_mock_results(
            xyxy_list=[[10.0, 20.0, 60.0, 120.0]],  # w=50, h=100
            cls_list=[0],
            conf_list=[0.8],
        )
        detections, _ = det._parse_detections(results)
        assert len(detections) == 1
        bbox, conf, cls = detections[0]
        assert bbox == [10.0, 20.0, 50.0, 100.0]  # [x1, y1, w, h]
        assert conf == pytest.approx(0.8)
        assert cls == 0

    def test_ball_class_goes_to_balls_list(self):
        """Ball class (32) is routed to balls list, not detections."""
        det = self._make_det()
        results = make_mock_results(
            xyxy_list=[[100.0, 100.0, 120.0, 120.0]],
            cls_list=[32],
            conf_list=[0.8],
        )
        detections, balls = det._parse_detections(results)
        assert detections == []
        assert len(balls) == 1
        assert balls[0] == [100.0, 100.0, 120.0, 120.0]

    def test_ball_no_size_filter_applied(self):
        """Balls are accepted regardless of bbox size (no min_player_w/h check)."""
        det = self._make_det()
        # Tiny ball bbox (5x5) — would fail player filter but should pass for ball
        results = make_mock_results(
            xyxy_list=[[50.0, 50.0, 55.0, 55.0]],
            cls_list=[32],
            conf_list=[0.9],
        )
        detections, balls = det._parse_detections(results)
        assert detections == []
        assert len(balls) == 1

    def test_mixed_player_and_ball_correctly_separated(self):
        """Frame with one player and one ball → correctly split."""
        det = self._make_det()
        results = make_mock_results(
            xyxy_list=[
                [0.0, 0.0, 50.0, 100.0],     # player (w=50, h=100)
                [200.0, 200.0, 215.0, 215.0], # ball
            ],
            cls_list=[0, 32],
            conf_list=[0.9, 0.8],
        )
        detections, balls = det._parse_detections(results)
        assert len(detections) == 1
        assert len(balls) == 1

    def test_unknown_class_ignored(self):
        """Class not in player_classes and not ball_class is silently ignored."""
        det = self._make_det()
        results = make_mock_results(
            xyxy_list=[[0.0, 0.0, 80.0, 120.0]],
            cls_list=[5],   # unknown class
            conf_list=[0.9],
        )
        detections, balls = det._parse_detections(results)
        assert detections == []
        assert balls == []
