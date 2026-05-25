import os
import sys
from pathlib import Path
from unittest.mock import MagicMock

# ---------------------------------------------------------------------------
# Ensure project root and backend/ are on sys.path so both 'ml' and 'app'
# packages are importable from any test regardless of working directory.
# ---------------------------------------------------------------------------
PROJECT_ROOT = str(Path(__file__).resolve().parents[1])
BACKEND_DIR = str(Path(__file__).resolve().parents[1] / "backend")

if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

# ---------------------------------------------------------------------------
# Mock heavy ML dependencies at sys.modules level BEFORE any ml.* import.
# This allows all tests to run without ultralytics, easyocr, deep_sort, etc.
# ---------------------------------------------------------------------------
_ultralytics = MagicMock()
_ultralytics.YOLO = MagicMock
sys.modules.setdefault("ultralytics", _ultralytics)

sys.modules.setdefault("easyocr", MagicMock())

_dsr = MagicMock()
sys.modules.setdefault("deep_sort_realtime", _dsr)
sys.modules.setdefault("deep_sort_realtime.deepsort_tracker", MagicMock())

sys.modules.setdefault("torch", MagicMock())
sys.modules.setdefault("torchvision", MagicMock())
sys.modules.setdefault("imageio_ffmpeg", MagicMock())

try:
    import cv2  # noqa: F401 — use real cv2 if available
except ImportError:
    sys.modules.setdefault("cv2", MagicMock())
