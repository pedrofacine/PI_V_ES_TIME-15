"""
Unit tests for pure helper methods of VideoPipeline.

No YOLO model is loaded. No video files are needed.
All tests use synthetic/fabricated data.
"""
import threading
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Config constants (imported directly so tests stay in sync with the source)
# ---------------------------------------------------------------------------
from ml.scripts.config import (
    GAP_TOLERANCE,
    MAX_PLAYER_ASPECT_RATIO,
    MIN_CLIP_FRAMES,
    SCOREBOARD_ZONE_BOTTOM,
    SCOREBOARD_ZONE_TOP,
    TORSO_Y_END,
    TORSO_Y_START,
)


# ---------------------------------------------------------------------------
# Fixture: VideoPipeline instance with all heavy deps mocked out
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def pipeline():
    """Create a VideoPipeline with every heavy dependency mocked."""
    with patch("ml.detector.YoloDetector"), \
         patch("ml.detector.BallDetector"), \
         patch("ml.scripts.jersey_reader.JerseyReader"), \
         patch("ml.scripts.ball_event_detector.BallEventDetector"), \
         patch("ml.scripts.kinematic_analyzer.KinematicAnalyzer"), \
         patch("ml.scripts.clip_writer.ClipWriter"), \
         patch("ml.scripts.color_extractor.ColorExtractor"):
        from ml.scripts.video_pipeline import VideoPipeline

        with patch.object(VideoPipeline, "__init__", lambda self: None):
            p = VideoPipeline()
            p._tl = threading.local()
            p._tl.logger = MagicMock()
            p._tl.session_id = "test-session"
            p.detector = MagicMock()
            p.ball_detector = MagicMock()
            p.jersey_reader = MagicMock()
            p.ball_event_detector = MagicMock()
            p.kinematic_analyzer = MagicMock()
            p.clip_writer = MagicMock()
            p.color_extractor = MagicMock()
            return p


# ===========================================================================
# _color_distance
# ===========================================================================

class TestColorDistance:
    def test_same_color_returns_zero(self, pipeline):
        dist = pipeline._color_distance("#ff0000", "#ff0000")
        assert dist == pytest.approx(0.0, abs=0.1)

    def test_black_white_large_distance(self, pipeline):
        dist = pipeline._color_distance("#000000", "#ffffff")
        assert dist > 50, f"Expected large distance between black and white, got {dist}"

    def test_invalid_hex_returns_999(self, pipeline):
        assert pipeline._color_distance("invalid", "#ffffff") == 999.0

    def test_both_invalid_returns_999(self, pipeline):
        assert pipeline._color_distance("not_a_color", "also_not") == 999.0

    def test_similar_colors_small_distance(self, pipeline):
        # Two shades of red that are close perceptually
        dist = pipeline._color_distance("#ff0000", "#ee0000")
        assert dist < 20, f"Similar reds should be close, got {dist}"

    def test_very_different_colors_large_distance(self, pipeline):
        dist = pipeline._color_distance("#ff0000", "#0000ff")
        assert dist > 30, f"Red vs blue should be a large distance, got {dist}"


# ===========================================================================
# _is_valid_player_detection
# ===========================================================================

class TestIsValidPlayerDetection:
    """
    Config snapshot used in calculations:
      SCOREBOARD_ZONE_TOP    = 0.18
      SCOREBOARD_ZONE_BOTTOM = 0.10
      MAX_PLAYER_ASPECT_RATIO= 1.5
      TORSO_Y_START          = 0.15
      TORSO_Y_END            = 0.55
    """

    def test_wide_bbox_rejected_by_aspect_ratio(self, pipeline):
        # w=200, h=50 → ratio=4.0 > 1.5
        bbox = (10, 10, 200, 50)
        assert pipeline._is_valid_player_detection(bbox, 720) is False

    def test_exact_aspect_ratio_threshold_rejected(self, pipeline):
        # w/h == MAX_PLAYER_ASPECT_RATIO exactly is NOT > so should pass aspect check,
        # but let us confirm a ratio just above is rejected
        w = int(MAX_PLAYER_ASPECT_RATIO * 100) + 1  # e.g. 151
        h = 100
        bbox = (10, 200, w, h)
        assert pipeline._is_valid_player_detection(bbox, 720) is False

    def test_player_torso_in_top_dead_zone_rejected(self, pipeline):
        """
        frame_h=720, dead_top = 720 * 0.18 = 129.6
        y1=0, h=80 → torso_y1 = 0 + 80*0.15 = 12.0 < 129.6 → rejected
        """
        bbox = (100, 0, 60, 80)
        assert pipeline._is_valid_player_detection(bbox, 720) is False

    def test_player_torso_in_bottom_dead_zone_rejected(self, pipeline):
        """
        frame_h=720, dead_bottom = 720*(1-0.10) = 648
        y1=620, h=80 → torso_y2 = 620 + 80*0.55 = 664 > 648 → rejected
        """
        bbox = (100, 620, 60, 80)
        assert pipeline._is_valid_player_detection(bbox, 720) is False

    def test_valid_player_in_center_accepted(self, pipeline):
        """
        frame_h=720, dead_top=129.6, dead_bottom=648
        y1=200, h=120
          torso_y1 = 200 + 120*0.15 = 218  > 129.6 ✓
          torso_y2 = 200 + 120*0.55 = 266  < 648   ✓
        w=60, h=120 → ratio=0.5 < 1.5 ✓
        """
        bbox = (100, 200, 60, 120)
        assert pipeline._is_valid_player_detection(bbox, 720) is True

    def test_zero_height_does_not_raise(self, pipeline):
        """bbox with h=0 must not crash (division-by-zero guard)."""
        # h=0 means w/h would divide by zero — the code guards with `h > 0`
        bbox = (100, 100, 50, 0)
        # Should not raise; result depends on position but must return bool
        result = pipeline._is_valid_player_detection(bbox, 720)
        assert isinstance(result, bool)

    def test_valid_player_small_frame(self, pipeline):
        """Works correctly on a smaller frame (e.g. 480p)."""
        # frame_h=480, dead_top=86.4, dead_bottom=432
        # y1=150, h=100 → torso_y1=165>86.4, torso_y2=205<432
        # w=40, h=100 → ratio=0.4 < 1.5
        bbox = (50, 150, 40, 100)
        assert pipeline._is_valid_player_detection(bbox, 480) is True


# ===========================================================================
# _group_frames_into_intervals
# ===========================================================================

class TestGroupFramesIntoIntervals:
    """
    Config snapshot:
      GAP_TOLERANCE  = 120  (frames)
      MIN_CLIP_FRAMES = 30  (frames, uses >= comparison)
    """

    def test_empty_input(self, pipeline):
        assert pipeline._group_frames_into_intervals([]) == []

    def test_single_long_clip(self, pipeline):
        frames = list(range(0, 100))  # 100 frames, well above MIN_CLIP_FRAMES=30
        intervals = pipeline._group_frames_into_intervals(frames)
        assert len(intervals) == 1
        assert intervals[0] == (0, 99)

    def test_gap_within_tolerance_joins_clips(self, pipeline):
        # gap = 80-60 = 20 frames which is <= GAP_TOLERANCE=120
        frames = list(range(0, 60)) + list(range(80, 140))
        intervals = pipeline._group_frames_into_intervals(frames)
        assert len(intervals) == 1

    def test_gap_exceeding_tolerance_splits_clips(self, pipeline):
        # gap = 250-60 = 190 frames > GAP_TOLERANCE=120
        frames = list(range(0, 60)) + list(range(250, 310))
        intervals = pipeline._group_frames_into_intervals(frames)
        assert len(intervals) == 2

    def test_short_group_discarded(self, pipeline):
        # Only 5 frames < MIN_CLIP_FRAMES=30 → discarded
        frames = [0, 1, 2, 3, 4]
        assert pipeline._group_frames_into_intervals(frames) == []

    def test_exactly_min_clip_frames_kept(self, pipeline):
        # Exactly MIN_CLIP_FRAMES=30 frames: span = 29 (0 to 29), 29 >= 30 is False → discarded
        # The check is (current_end - current_start) >= MIN_CLIP_FRAMES
        # span of 30 frames 0..29 → end-start = 29, 29 >= 30 is False → discarded
        frames = list(range(0, 30))
        result = pipeline._group_frames_into_intervals(frames)
        assert result == []

    def test_span_equal_to_min_clip_frames_kept(self, pipeline):
        # span = 30 (frames 0 and 30) → end-start = 30 >= 30 → kept
        frames = list(range(0, 31))  # 0..30 → span=30
        result = pipeline._group_frames_into_intervals(frames)
        assert len(result) == 1
        assert result[0] == (0, 30)

    def test_multiple_valid_clips(self, pipeline):
        # Two groups each with span > 30, separated by gap > 120
        frames = list(range(0, 60)) + list(range(300, 360))
        intervals = pipeline._group_frames_into_intervals(frames)
        assert len(intervals) == 2
        assert intervals[0] == (0, 59)
        assert intervals[1] == (300, 359)

    def test_three_groups_middle_short_discarded(self, pipeline):
        # group1: 0..59 (span=59 ✓), group2: 200..204 (span=4 ✗), group3: 400..459 (span=59 ✓)
        frames = list(range(0, 60)) + list(range(200, 205)) + list(range(400, 460))
        intervals = pipeline._group_frames_into_intervals(frames)
        assert len(intervals) == 2


# ===========================================================================
# _target_in_frame
# ===========================================================================

class TestTargetInFrame:
    def test_target_present_in_frame(self, pipeline):
        meta = {5: {"tracks": [[10, 20, 50, 80, "tid_42"]], "balls": []}}
        assert pipeline._target_in_frame(meta, 5, {"tid_42"}) is True

    def test_target_absent_different_id(self, pipeline):
        meta = {5: {"tracks": [[10, 20, 50, 80, "tid_99"]], "balls": []}}
        assert pipeline._target_in_frame(meta, 5, {"tid_42"}) is False

    def test_frame_not_in_metadata(self, pipeline):
        meta = {}
        assert pipeline._target_in_frame(meta, 5, {"tid_42"}) is False

    def test_multiple_tracks_one_matches(self, pipeline):
        meta = {
            10: {
                "tracks": [
                    [10, 20, 50, 80, "tid_1"],
                    [60, 30, 90, 100, "tid_42"],
                ],
                "balls": [],
            }
        }
        assert pipeline._target_in_frame(meta, 10, {"tid_42"}) is True

    def test_multiple_targets_any_match(self, pipeline):
        meta = {3: {"tracks": [[10, 20, 50, 80, "tid_7"]], "balls": []}}
        assert pipeline._target_in_frame(meta, 3, {"tid_7", "tid_42"}) is True

    def test_empty_tracks_list(self, pipeline):
        meta = {1: {"tracks": [], "balls": []}}
        assert pipeline._target_in_frame(meta, 1, {"tid_42"}) is False

    def test_track_id_matched_as_string(self, pipeline):
        # track_id stored as integer but target_ids are strings (or vice versa)
        meta = {0: {"tracks": [[0, 0, 10, 10, 42]], "balls": []}}
        # The implementation does str(tid) in target_track_ids
        assert pipeline._target_in_frame(meta, 0, {"42"}) is True


# ===========================================================================
# _get_safe_fps (static method)
# ===========================================================================

class TestGetSafeFps:
    """
    Logic: return fps if 10 <= fps <= 120, else return 30.0
    Code: `if not fps or fps < 10 or fps > 120: return 30.0`
    """

    def test_valid_fps_returned_as_is(self):
        mock_cap = MagicMock()
        mock_cap.get.return_value = 30.0
        from ml.scripts.video_pipeline import VideoPipeline
        assert VideoPipeline._get_safe_fps(mock_cap) == 30.0

    def test_zero_fps_returns_fallback(self):
        mock_cap = MagicMock()
        mock_cap.get.return_value = 0.0
        from ml.scripts.video_pipeline import VideoPipeline
        assert VideoPipeline._get_safe_fps(mock_cap) == 30.0

    def test_fps_above_120_returns_fallback(self):
        mock_cap = MagicMock()
        mock_cap.get.return_value = 999.0
        from ml.scripts.video_pipeline import VideoPipeline
        assert VideoPipeline._get_safe_fps(mock_cap) == 30.0

    def test_fps_below_10_returns_fallback(self):
        mock_cap = MagicMock()
        mock_cap.get.return_value = 5.0
        from ml.scripts.video_pipeline import VideoPipeline
        assert VideoPipeline._get_safe_fps(mock_cap) == 30.0

    def test_fps_at_boundary_10_valid(self):
        mock_cap = MagicMock()
        mock_cap.get.return_value = 10.0
        from ml.scripts.video_pipeline import VideoPipeline
        assert VideoPipeline._get_safe_fps(mock_cap) == 10.0

    def test_fps_at_boundary_120_valid(self):
        mock_cap = MagicMock()
        mock_cap.get.return_value = 120.0
        from ml.scripts.video_pipeline import VideoPipeline
        assert VideoPipeline._get_safe_fps(mock_cap) == 120.0

    def test_fps_25_valid(self):
        mock_cap = MagicMock()
        mock_cap.get.return_value = 25.0
        from ml.scripts.video_pipeline import VideoPipeline
        assert VideoPipeline._get_safe_fps(mock_cap) == 25.0

    def test_fps_60_valid(self):
        mock_cap = MagicMock()
        mock_cap.get.return_value = 60.0
        from ml.scripts.video_pipeline import VideoPipeline
        assert VideoPipeline._get_safe_fps(mock_cap) == 60.0
