"""
Integration tests for internal pipeline steps.

Tests _resolve_player_ids and _compute_clip_intervals with synthetic data.
No video files, no YOLO, no real models — pure logic tested end-to-end.
"""
import threading
from collections import Counter
from unittest.mock import MagicMock

import pytest

from ml.scripts.config import (
    MIN_OCR_VOTES,
    MAX_DISTINCT_READINGS,
    GAP_TOLERANCE,
    MIN_CLIP_FRAMES,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_pipeline():
    """Create a bare VideoPipeline instance with all heavy deps mocked."""
    from ml.scripts.video_pipeline import VideoPipeline

    p = VideoPipeline.__new__(VideoPipeline)
    p._tl = threading.local()
    p._tl.logger = MagicMock()
    p._tl.session_id = "test"
    p.kinematic_analyzer = MagicMock()
    p.kinematic_analyzer.analyze.return_value = []
    p.ball_event_detector = MagicMock()
    p.ball_event_detector.detect.return_value = []
    return p


def make_jersey_map(track_id: str, number, votes: int) -> dict:
    """Build a jersey_map with a single track and a single number/votes."""
    return {track_id: Counter({number: votes})}


def make_meta(frame_indices, track_id: str = "t1") -> dict:
    """Build video_metadata with the target track present in the given frames."""
    return {
        i: {
            "tracks": [[10.0, 20.0, 50.0, 80.0, track_id]],
            "balls": [],
        }
        for i in frame_indices
    }


# ---------------------------------------------------------------------------
# _resolve_player_ids tests
# ---------------------------------------------------------------------------

class TestResolvePlayerIds:

    def test_resolve_player_ids_found(self):
        """Track with votes >= MIN_OCR_VOTES resolves correctly."""
        p = make_pipeline()
        jersey_map = make_jersey_map("t1", 10, MIN_OCR_VOTES)

        result = p._resolve_player_ids(
            jersey_map=jersey_map,
            target_number=10,
            target_signature=None,
            debug=False,
        )

        assert result == {"t1"}

    def test_resolve_player_ids_fallback(self):
        """Track with only 1 vote (below MIN_OCR_VOTES) is accepted via fallback
        because it is still the top-voted number for that track."""
        p = make_pipeline()
        # 1 vote, which is below MIN_OCR_VOTES (=2), forces the fallback path
        jersey_map = make_jersey_map("t1", 10, 1)

        result = p._resolve_player_ids(
            jersey_map=jersey_map,
            target_number=10,
            target_signature=None,
            debug=False,
        )

        assert result == {"t1"}

    def test_resolve_player_ids_not_found(self):
        """Raises ValueError when target number is not in jersey_map."""
        p = make_pipeline()
        jersey_map = make_jersey_map("t1", 7, MIN_OCR_VOTES)

        with pytest.raises(ValueError, match="Jogador alvo não encontrado"):
            p._resolve_player_ids(
                jersey_map=jersey_map,
                target_number=10,
                target_signature=None,
                debug=False,
            )

    def test_resolve_player_ids_filters_noisy_tracks(self):
        """Tracks with more than MAX_DISTINCT_READINGS different numbers are discarded."""
        p = make_pipeline()

        # Create a noisy track that has MAX_DISTINCT_READINGS+1 different numbers
        noisy_counter = Counter(
            {i: 1 for i in range(MAX_DISTINCT_READINGS + 1)}
        )
        # Add target number 10 in the noisy counter so it would match if not discarded
        noisy_counter[10] = 1

        jersey_map = {"t1": noisy_counter}

        with pytest.raises(ValueError, match="Jogador alvo não encontrado"):
            p._resolve_player_ids(
                jersey_map=jersey_map,
                target_number=10,
                target_signature=None,
                debug=False,
            )

    def test_resolve_player_ids_with_signature(self):
        """Resolves by signature string when target_signature is provided."""
        p = make_pipeline()
        signature = "10_#ff0000"
        jersey_map = {"t1": Counter({signature: MIN_OCR_VOTES})}

        result = p._resolve_player_ids(
            jersey_map=jersey_map,
            target_number=10,
            target_signature=signature,
            debug=False,
        )

        assert result == {"t1"}

    def test_resolve_player_ids_multiple_tracks_selects_correct(self):
        """When multiple tracks exist, only the one matching target number is returned."""
        p = make_pipeline()
        jersey_map = {
            "t1": Counter({10: MIN_OCR_VOTES}),
            "t2": Counter({7: MIN_OCR_VOTES}),
            "t3": Counter({10: MIN_OCR_VOTES}),
        }

        result = p._resolve_player_ids(
            jersey_map=jersey_map,
            target_number=10,
            target_signature=None,
            debug=False,
        )

        assert result == {"t1", "t3"}


# ---------------------------------------------------------------------------
# _compute_clip_intervals tests
# ---------------------------------------------------------------------------

class TestComputeClipIntervals:

    def test_compute_clip_intervals_empty_player(self):
        """When target track never appears in video_metadata, clip_intervals is []."""
        p = make_pipeline()

        # Build metadata with a DIFFERENT track (not the target)
        video_metadata = make_meta(range(0, 100), track_id="other_track")

        target_frames, events, clip_intervals = p._compute_clip_intervals(
            video_metadata=video_metadata,
            target_track_ids={"t1"},
            start_frame=0,
            processed_total=100,
            fps=30.0,
        )

        assert clip_intervals == []
        assert target_frames == []

    def test_compute_clip_intervals_full_flow(self):
        """Target appearing in many consecutive frames produces at least one clip."""
        p = make_pipeline()

        # Target appears every other frame (0, 2, 4, ..., 98) — 50 frames
        frame_indices = list(range(0, 100, 2))
        video_metadata = make_meta(frame_indices, track_id="t1")

        target_frames, events, clip_intervals = p._compute_clip_intervals(
            video_metadata=video_metadata,
            target_track_ids={"t1"},
            start_frame=0,
            processed_total=100,
            fps=30.0,
        )

        # The frames span 0-98, gap between consecutive is 2 << GAP_TOLERANCE
        # Span = 98 - 0 = 98 >= MIN_CLIP_FRAMES (30), so exactly 1 interval
        assert len(clip_intervals) == 1
        assert clip_intervals[0][0] == 0
        assert clip_intervals[0][1] == 98

    def test_group_frames_produces_padded_clips(self):
        """_compute_clip_intervals correctly delegates grouping to _group_frames_into_intervals."""
        p = make_pipeline()

        # Two separate runs of frames far apart (> GAP_TOLERANCE)
        group1 = list(range(0, 60))    # span=59 >= 30 -> valid clip
        group2 = list(range(300, 360)) # span=59 >= 30 -> valid clip, gap=240 > 120
        all_frames = group1 + group2
        video_metadata = make_meta(all_frames, track_id="t1")

        target_frames, events, clip_intervals = p._compute_clip_intervals(
            video_metadata=video_metadata,
            target_track_ids={"t1"},
            start_frame=0,
            processed_total=360,
            fps=30.0,
        )

        assert len(clip_intervals) == 2
        assert clip_intervals[0] == (0, 59)
        assert clip_intervals[1] == (300, 359)

    def test_compute_clip_intervals_delegates_to_mocked_analyzers(self):
        """Verifies that kinematic_analyzer.analyze and ball_event_detector.detect are called."""
        p = make_pipeline()
        video_metadata = make_meta(range(0, 60), track_id="t1")

        p._compute_clip_intervals(
            video_metadata=video_metadata,
            target_track_ids={"t1"},
            start_frame=0,
            processed_total=60,
            fps=30.0,
        )

        p.kinematic_analyzer.analyze.assert_called_once()
        p.ball_event_detector.detect.assert_called_once()
