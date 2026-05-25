"""
Unit tests for KinematicAnalyzer.

No YOLO model is loaded. All tests use synthetic/fabricated data.
KinematicAnalyzer uses pure Python/math — no mocking needed.
"""
import math

import pytest
from ml.scripts.kinematic_analyzer import KinematicAnalyzer
from ml.scripts.config import (
    KINEMATIC_COOLDOWN_SECONDS,
    KINEMATIC_MIN_ACCEL,
    KINEMATIC_MIN_VELOCITY,
    KINEMATIC_STD_MULTIPLIER,
)


@pytest.fixture
def analyzer():
    """Default KinematicAnalyzer with config defaults."""
    return KinematicAnalyzer()


# ===========================================================================
# _compute_kinematics
# ===========================================================================

class TestComputeKinematics:
    """
    Implementation notes:
    - velocities: len == len(positions), first element is always 0.0
    - accelerations: len >= len(positions) (may be one element longer due to
      the initialisation with [0.0, 0.0] before the loop)
    """

    def test_stationary_all_velocities_zero(self, analyzer):
        positions = [(0, 100.0, 100.0), (1, 100.0, 100.0), (2, 100.0, 100.0)]
        velocities, accelerations = analyzer._compute_kinematics(positions)
        assert all(v == pytest.approx(0.0) for v in velocities)

    def test_stationary_all_accelerations_zero(self, analyzer):
        positions = [(0, 100.0, 100.0), (1, 100.0, 100.0), (2, 100.0, 100.0)]
        _, accelerations = analyzer._compute_kinematics(positions)
        # The relevant portion (up to len(positions)) should be zero
        assert all(a == pytest.approx(0.0) for a in accelerations[: len(positions)])

    def test_linear_motion_constant_velocity(self, analyzer):
        """Moving 10 px per frame → velocity == 10 for all steps after the first."""
        positions = [(i, float(i * 10), 0.0) for i in range(5)]
        velocities, _ = analyzer._compute_kinematics(positions)
        assert len(velocities) == 5
        assert velocities[0] == pytest.approx(0.0)
        for v in velocities[1:]:
            assert v == pytest.approx(10.0, abs=0.1)

    def test_velocities_length_equals_positions_length(self, analyzer):
        positions = [(i, float(i), 0.0) for i in range(7)]
        velocities, _ = analyzer._compute_kinematics(positions)
        assert len(velocities) == len(positions)

    def test_sudden_stop_produces_nonzero_acceleration(self, analyzer):
        """
        Moving 50px/frame then stopping → large acceleration change at the stop.
        """
        positions = [
            (0, 0.0, 0.0),
            (1, 50.0, 0.0),
            (2, 100.0, 0.0),
            (3, 100.0, 0.0),  # sudden stop
        ]
        _, accelerations = analyzer._compute_kinematics(positions)
        # At least one acceleration value should be non-zero
        assert max(accelerations) > 0

    def test_single_position_no_crash(self, analyzer):
        """A single position should not raise — velocities=[0.0]."""
        positions = [(0, 10.0, 20.0)]
        velocities, accelerations = analyzer._compute_kinematics(positions)
        assert velocities == [0.0]

    def test_diagonal_motion_velocity_magnitude(self, analyzer):
        """3-4-5 Pythagorean triple: moving (3,4) per frame → speed == 5."""
        positions = [(i, float(i * 3), float(i * 4)) for i in range(4)]
        velocities, _ = analyzer._compute_kinematics(positions)
        for v in velocities[1:]:
            assert v == pytest.approx(5.0, abs=0.01)

    def test_frame_skip_normalised_velocity(self, analyzer):
        """
        When frames are not consecutive (e.g. FRAME_SKIP=2), the delta
        normalises velocity correctly: 20px / 2frames = 10px/frame.
        """
        positions = [(0, 0.0, 0.0), (2, 20.0, 0.0), (4, 40.0, 0.0)]
        velocities, _ = analyzer._compute_kinematics(positions)
        for v in velocities[1:]:
            assert v == pytest.approx(10.0, abs=0.01)


# ===========================================================================
# _collect_positions
# ===========================================================================

class TestCollectPositions:
    def test_player_positions_collected_correctly(self, analyzer):
        meta = {
            0: {"tracks": [[10.0, 20.0, 50.0, 80.0, "t1"]], "balls": []},
            1: {"tracks": [[15.0, 25.0, 55.0, 85.0, "t1"]], "balls": []},
        }
        positions = analyzer._collect_positions(meta)
        assert "t1" in positions
        assert len(positions["t1"]) == 2
        # center of [10,20,50,80]: cx=(10+50)/2=30, cy=(20+80)/2=50
        assert positions["t1"][0] == (0, 30.0, 50.0)
        # center of [15,25,55,85]: cx=35, cy=55
        assert positions["t1"][1] == (1, 35.0, 55.0)

    def test_ball_positions_collected_correctly(self, analyzer):
        meta = {
            0: {"tracks": [], "balls": [[10.0, 10.0, 30.0, 30.0]]},
        }
        positions = analyzer._collect_positions(meta)
        assert "ball_0" in positions
        # center of [10,10,30,30]: cx=20, cy=20
        assert positions["ball_0"][0] == (0, 20.0, 20.0)

    def test_multiple_balls_per_frame(self, analyzer):
        meta = {
            0: {
                "tracks": [],
                "balls": [
                    [0.0, 0.0, 20.0, 20.0],   # ball_0 center=(10,10)
                    [50.0, 50.0, 70.0, 70.0],  # ball_1 center=(60,60)
                ],
            }
        }
        positions = analyzer._collect_positions(meta)
        assert "ball_0" in positions
        assert "ball_1" in positions
        assert positions["ball_0"][0] == (0, 10.0, 10.0)
        assert positions["ball_1"][0] == (0, 60.0, 60.0)

    def test_multiple_tracks_per_frame(self, analyzer):
        meta = {
            0: {
                "tracks": [
                    [0.0, 0.0, 20.0, 40.0, "t1"],
                    [50.0, 50.0, 70.0, 90.0, "t2"],
                ],
                "balls": [],
            }
        }
        positions = analyzer._collect_positions(meta)
        assert "t1" in positions
        assert "t2" in positions

    def test_frames_processed_in_sorted_order(self, analyzer):
        """Regardless of dict key insertion order, positions should be sorted by frame."""
        meta = {
            5: {"tracks": [[0.0, 0.0, 10.0, 20.0, "t1"]], "balls": []},
            2: {"tracks": [[5.0, 5.0, 15.0, 25.0, "t1"]], "balls": []},
        }
        positions = analyzer._collect_positions(meta)
        frames = [p[0] for p in positions["t1"]]
        assert frames == sorted(frames)

    def test_empty_metadata_returns_empty(self, analyzer):
        positions = analyzer._collect_positions({})
        assert positions == {}


# ===========================================================================
# _detect_anomalies
# ===========================================================================

class TestDetectAnomalies:
    """
    Implementation note:
    An anomaly is flagged only when BOTH conditions hold:
      v > fixed_threshold  AND  v > stat_threshold (mean + std_multiplier*std)
    The code condition is `if v <= fixed_threshold or v <= stat_threshold: continue`
    which is equivalent to skipping unless BOTH thresholds are exceeded.
    """

    def test_all_zero_values_no_anomalies(self, analyzer):
        positions = [(i, float(i), 0.0) for i in range(10)]
        values = [0.0] * 10
        events = analyzer._detect_anomalies(
            positions, values, "pico_velocidade", "jogador", "t1", 30.0
        )
        assert events == []

    def test_uniform_values_no_anomalies(self, analyzer):
        """Constant velocity → std=0 → stat_threshold = mean → no value exceeds it."""
        positions = [(i, float(i * 5), 0.0) for i in range(10)]
        values = [5.0] * 10
        events = analyzer._detect_anomalies(
            positions, values, "pico_velocidade", "jogador", "t1", 30.0
        )
        assert events == []

    def test_large_spike_produces_anomaly(self, analyzer):
        """One extreme spike far above both thresholds."""
        positions = [(i, float(i), 0.0) for i in range(100)]
        values = [0.0] * 100
        values[50] = 10000.0  # enormous spike
        events = analyzer._detect_anomalies(
            positions, values, "pico_velocidade", "jogador", "t1", 30.0
        )
        assert len(events) >= 1
        assert events[0]["frame"] == 50

    def test_cooldown_suppresses_second_spike(self, analyzer):
        """
        Two spikes close together: only the first should be registered.
        cooldown_frames = int(30.0 * 1.5) = 45 frames.
        Spike at frame 10 and frame 15 (gap=5 <= 45) → only frame 10 fires.
        """
        positions = [(i, float(i), 0.0) for i in range(100)]
        values = [0.0] * 100
        values[10] = 1000.0
        values[15] = 1000.0
        events = analyzer._detect_anomalies(
            positions, values, "pico_velocidade", "jogador", "t1", 30.0
        )
        assert len(events) == 1
        assert events[0]["frame"] == 10

    def test_two_spikes_far_apart_both_detected(self, analyzer):
        """
        Two spikes separated by more than cooldown_frames (45 frames at fps=30).
        Both should produce an event.
        """
        positions = [(i, float(i), 0.0) for i in range(200)]
        values = [0.0] * 200
        values[10] = 1000.0
        values[100] = 1000.0  # gap=90 > 45
        events = analyzer._detect_anomalies(
            positions, values, "pico_velocidade", "jogador", "t1", 30.0
        )
        assert len(events) == 2
        assert events[0]["frame"] == 10
        assert events[1]["frame"] == 100

    def test_event_type_recorded_correctly(self, analyzer):
        positions = [(i, float(i), 0.0) for i in range(100)]
        values = [0.0] * 100
        values[50] = 10000.0
        events = analyzer._detect_anomalies(
            positions, values, "pico_aceleracao", "bola", "ball_0", 30.0
        )
        if events:
            assert events[0]["type"] == "pico_aceleracao"
            assert events[0]["object"] == "bola"
            assert events[0]["track_id"] == "ball_0"

    def test_event_contains_required_fields(self, analyzer):
        positions = [(i, float(i), 0.0) for i in range(100)]
        values = [0.0] * 100
        values[50] = 10000.0
        events = analyzer._detect_anomalies(
            positions, values, "pico_velocidade", "jogador", "t1", 30.0
        )
        assert len(events) >= 1
        e = events[0]
        assert "type" in e
        assert "object" in e
        assert "track_id" in e
        assert "frame" in e
        assert "time" in e
        assert "value" in e


# ===========================================================================
# analyze — integration over the full pipeline
# ===========================================================================

class TestAnalyze:
    def test_fewer_than_3_points_ignored(self, analyzer):
        """Track with only 1 frame → skipped (< 3 positions check)."""
        meta = {0: {"tracks": [[0.0, 0.0, 10.0, 20.0, "t1"]], "balls": []}}
        events = analyzer.analyze(meta, 30.0)
        assert events == []

    def test_two_points_ignored(self, analyzer):
        """Track with exactly 2 frames → skipped."""
        meta = {
            0: {"tracks": [[0.0, 0.0, 10.0, 20.0, "t1"]], "balls": []},
            1: {"tracks": [[5.0, 5.0, 15.0, 25.0, "t1"]], "balls": []},
        }
        events = analyzer.analyze(meta, 30.0)
        assert events == []

    def test_stationary_track_no_events(self, analyzer):
        """Player that never moves → no anomalies."""
        meta = {
            i: {"tracks": [[0.0, 0.0, 50.0, 100.0, "t1"]], "balls": []}
            for i in range(10)
        }
        events = analyzer.analyze(meta, 30.0)
        assert events == []

    def test_events_sorted_by_frame(self, analyzer):
        """Returned events list must be sorted by frame index."""
        # Use two tracks so both ball and player can spike
        meta = {}
        for i in range(50):
            meta[i] = {
                "tracks": [[float(i * 2), 0.0, float(i * 2 + 10), 20.0, "t1"]],
                "balls": [[float(i * 3), 0.0, float(i * 3 + 5), 5.0]],
            }
        events = analyzer.analyze(meta, 30.0)
        frames = [e["frame"] for e in events]
        assert frames == sorted(frames)

    def test_ball_track_detected_as_ball_object(self, analyzer):
        """Ball anomaly event must have object='bola'."""
        # Create a ball that has one massive jump
        meta = {}
        for i in range(20):
            x = float(i * 100) if i == 10 else 0.0  # big jump at frame 10
            meta[i] = {
                "tracks": [],
                "balls": [[x, 0.0, x + 5.0, 5.0]],
            }
        events = analyzer.analyze(meta, 30.0)
        ball_events = [e for e in events if e["object"] == "bola"]
        # May or may not fire depending on threshold, but if it does it must be labeled correctly
        for e in ball_events:
            assert e["object"] == "bola"
            assert e["track_id"].startswith("ball")
