"""
Unit tests for BallEventDetector.

No YOLO model is loaded. All tests use synthetic/fabricated data.
BallEventDetector uses pure Python/math — no mocking needed.
"""
import pytest
from ml.scripts.ball_event_detector import BallEventDetector
from ml.scripts.config import (
    BALL_IOU_THRESHOLD,
    BALL_PROXIMITY_PAD,
    EVENT_MIN_GAP_SECONDS,
)


@pytest.fixture
def detector():
    """Default BallEventDetector with config defaults."""
    return BallEventDetector()


# ===========================================================================
# _iou
# ===========================================================================

class TestIou:
    def test_no_overlap_returns_zero(self, detector):
        a = [0, 0, 10, 10]
        b = [20, 20, 30, 30]
        assert detector._iou(a, b) == 0.0

    def test_full_overlap_same_box_returns_one(self, detector):
        a = [0, 0, 10, 10]
        assert detector._iou(a, a) == pytest.approx(1.0)

    def test_partial_overlap(self, detector):
        # a=[0,0,10,10] area=100, b=[5,5,15,15] area=100
        # intersection: [5,5,10,10] area=25
        # union = 100 + 100 - 25 = 175
        a = [0, 0, 10, 10]
        b = [5, 5, 15, 15]
        expected = 25 / 175
        assert detector._iou(a, b) == pytest.approx(expected, abs=0.01)

    def test_touching_edges_no_overlap(self, detector):
        # Boxes that share exactly one edge (intersection area=0)
        a = [0, 0, 10, 10]
        b = [10, 0, 20, 10]
        assert detector._iou(a, b) == 0.0

    def test_one_inside_another(self, detector):
        # small box fully inside larger box
        outer = [0, 0, 100, 100]  # area=10000
        inner = [25, 25, 75, 75]  # area=2500
        # intersection = inner area = 2500, union = 10000
        expected = 2500 / 10000
        assert detector._iou(outer, inner) == pytest.approx(expected, abs=0.001)

    def test_symmetry(self, detector):
        a = [0, 0, 10, 20]
        b = [5, 10, 15, 30]
        assert detector._iou(a, b) == pytest.approx(detector._iou(b, a), abs=1e-9)


# ===========================================================================
# _is_ball_near_player
# ===========================================================================

class TestIsBallNearPlayer:
    """
    Config snapshot:
      BALL_IOU_THRESHOLD     = 0.01
      BALL_PROXIMITY_PAD     = 0.2
      BALL_PROXIMITY_THRESHOLD = 0.15
    """

    def test_direct_iou_overlap_detected(self, detector):
        # Ball fully inside player bbox → IoU >> threshold
        player = [0.0, 0.0, 100.0, 200.0]
        ball = [40.0, 40.0, 60.0, 60.0]
        assert detector._is_ball_near_player(player, ball) is True

    def test_ball_center_inside_expanded_bbox(self, detector):
        """
        player: x1=100, y1=100, x2=150, y2=200 → w=50, h=100
        expanded with pad=0.2:
          x1 = 100 - 50*0.2 = 90
          y1 = 100 - 100*0.2 = 80
          x2 = 150 + 50*0.2 = 160
          y2 = 200 + 100*0.2 = 220
        ball center at (120, 210) is inside expanded [90,80,160,220] ✓
        """
        player = [100.0, 100.0, 150.0, 200.0]
        ball = [115.0, 205.0, 125.0, 215.0]  # center=(120, 210)
        assert detector._is_ball_near_player(player, ball) is True

    def test_ball_far_away_not_detected(self, detector):
        player = [0.0, 0.0, 50.0, 100.0]
        ball = [500.0, 500.0, 520.0, 520.0]
        assert detector._is_ball_near_player(player, ball) is False

    def test_ball_outside_expanded_but_within_proportional_distance(self, detector):
        """
        player: x1=0, y1=0, x2=100, y2=200 → w=100, h=200
        expanded with pad=0.2:
          [0-20, 0-40, 100+20, 200+40] = [-20, -40, 120, 240]
        threshold = max(100,200) * 0.15 = 30px
        ball at [130, 120, 140, 130] → center=(135, 125)
          dx = max(-20-135, 0, 135-120) = 15
          dy = 0 (125 inside -40..240)
          dist² = 225 <= 900 ✓
        """
        player = [0.0, 0.0, 100.0, 200.0]
        ball = [130.0, 120.0, 140.0, 130.0]  # center=(135, 125)
        assert detector._is_ball_near_player(player, ball) is True

    def test_ball_just_outside_all_criteria_not_detected(self, detector):
        """Ball that is clearly outside all three detection criteria."""
        player = [0.0, 0.0, 50.0, 100.0]
        # w=50, h=100; expanded=[-10,-20,60,120]; threshold=max(50,100)*0.15=15
        # ball center at (200, 200): dx=200-60=140, dy=200-120=80
        # dist²=140²+80²=19600+6400=26000 >> 15²=225
        ball = [195.0, 195.0, 205.0, 205.0]
        assert detector._is_ball_near_player(player, ball) is False


# ===========================================================================
# detect — integration-level tests on pure logic
# ===========================================================================

class TestDetect:
    def test_no_balls_in_frame_returns_no_events(self, detector):
        fps = 30.0
        meta = {0: {"tracks": [[0.0, 0.0, 50.0, 100.0, "t1"]], "balls": []}}
        events = detector.detect([0], meta, {"t1"}, fps)
        assert events == []

    def test_no_target_tracks_returns_no_events(self, detector):
        fps = 30.0
        # Frame has a ball but the player track doesn't match target_ids
        meta = {0: {
            "tracks": [[0.0, 0.0, 50.0, 100.0, "other_player"]],
            "balls": [[20.0, 20.0, 40.0, 40.0]],
        }}
        events = detector.detect([0], meta, {"t1"}, fps)
        assert events == []

    def test_single_touch_detected(self, detector):
        fps = 30.0
        # Ball overlapping player in one frame
        meta = {0: {
            "tracks": [[0.0, 0.0, 50.0, 100.0, "t1"]],
            "balls": [[10.0, 10.0, 40.0, 40.0]],
        }}
        events = detector.detect([0], meta, {"t1"}, fps)
        assert len(events) >= 1
        assert events[0]["type"] == "toque"
        assert events[0]["frame"] == 0

    def test_cooldown_prevents_duplicate_events(self, detector):
        """
        With fps=30 and min_gap_seconds=1.0, gap_frames=30.
        Frames 0..198 (step 2) each have ball near player.
        Events should be separated by at least 30 frames.
        """
        fps = 30.0
        target_ids = {"t1"}
        player_box = [0.0, 0.0, 50.0, 100.0]
        ball_box = [10.0, 10.0, 40.0, 40.0]
        meta = {}
        target_frames = list(range(0, 200, 2))
        for f in target_frames:
            meta[f] = {
                "tracks": [[player_box[0], player_box[1], player_box[2], player_box[3], "t1"]],
                "balls": [ball_box],
            }
        events = detector.detect(target_frames, meta, target_ids, fps)
        assert len(events) >= 1
        # Verify cooldown: no two events within min_gap_seconds*fps frames
        for i in range(1, len(events)):
            gap = events[i]["frame"] - events[i - 1]["frame"]
            assert gap >= fps * detector.min_gap_seconds

    def test_event_time_is_frame_over_fps(self, detector):
        fps = 25.0
        meta = {50: {
            "tracks": [[0.0, 0.0, 50.0, 100.0, "t1"]],
            "balls": [[10.0, 10.0, 40.0, 40.0]],
        }}
        events = detector.detect([50], meta, {"t1"}, fps)
        if events:
            assert events[0]["time"] == pytest.approx(50 / 25.0)

    def test_empty_target_frames_returns_empty(self, detector):
        events = detector.detect([], {}, {"t1"}, 30.0)
        assert events == []

    def test_two_separated_touches_both_detected(self, detector):
        """
        Two touches separated by more than EVENT_MIN_GAP_SECONDS.
        Both should produce an event.
        """
        fps = 30.0
        gap = int(fps * EVENT_MIN_GAP_SECONDS) + 5  # safely past the cooldown
        frame_a = 0
        frame_b = frame_a + gap
        player_box = [0.0, 0.0, 50.0, 100.0]
        ball_box = [10.0, 10.0, 40.0, 40.0]
        meta = {
            frame_a: {"tracks": [[*player_box, "t1"]], "balls": [ball_box]},
            frame_b: {"tracks": [[*player_box, "t1"]], "balls": [ball_box]},
        }
        events = detector.detect([frame_a, frame_b], meta, {"t1"}, fps)
        assert len(events) == 2
