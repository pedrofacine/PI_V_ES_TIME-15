#!/usr/bin/env python
"""
Benchmark script: roda o pipeline SmartScout num vídeo real e coleta métricas.

Uso:
    python benchmark/benchmark_model.py <video_path> <target_number>

Saída:
    benchmark/benchmark_report.json
"""
import sys
import json
import time
from pathlib import Path
from datetime import datetime

# Add project root and backend to path
PROJECT_ROOT = str(Path(__file__).resolve().parents[1])
BACKEND_DIR = str(Path(__file__).resolve().parents[1] / "backend")
for p in [PROJECT_ROOT, BACKEND_DIR]:
    if p not in sys.path:
        sys.path.insert(0, p)


def run_benchmark(video_path: str, target_number: int) -> dict:
    from ml.scripts.video_pipeline import VideoPipeline

    pipeline = VideoPipeline()
    output_dir = str(Path(__file__).parent / "benchmark_output")
    Path(output_dir).mkdir(exist_ok=True)

    ball_touches = 0

    def on_clip_generated(clip_dict):
        nonlocal ball_touches
        ball_touches += len(clip_dict.get("events", []))

    start = time.time()
    clips = pipeline.process(
        video_path=video_path,
        target_number=target_number,
        output_dir=output_dir,
        on_clip_generated=on_clip_generated,
        debug=False,
    )
    elapsed = time.time() - start

    total_clips = len(clips)

    report = {
        "video": Path(video_path).name,
        "target_number": target_number,
        "timestamp": datetime.now().isoformat(),
        "events": {
            "ball_touches": ball_touches,
            "kinematic_anomalies": 0,  # not exposed by process() return value
        },
        "performance": {
            "total_clips": total_clips,
            "elapsed_seconds": round(elapsed, 2),
            "throughput_fps": None,  # filled below if we can estimate
        },
        "clips": [
            {
                "path": c["path"],
                "start_ts": c["start_ts"],
                "end_ts": c["end_ts"],
                "duration_s": round(c["end_ts"] - c["start_ts"], 2),
                "events": c.get("events", []),
            }
            for c in clips
        ],
    }

    return report


def print_summary(report: dict) -> None:
    """Print a human-readable summary of the benchmark results."""
    print("\n" + "=" * 55)
    print("         SMARTSCOUT — RELATÓRIO DE BENCHMARK")
    print("=" * 55)
    print(f"  Vídeo            : {report['video']}")
    print(f"  Jogador alvo     : #{report['target_number']}")
    print(f"  Timestamp        : {report['timestamp']}")
    print("-" * 55)
    print(f"  Clipes gerados   : {report['performance']['total_clips']}")
    print(f"  Toques de bola   : {report['events']['ball_touches']}")
    print(f"  Tempo total      : {report['performance']['elapsed_seconds']}s")
    print("=" * 55 + "\n")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Uso: python benchmark/benchmark_model.py <video_path> <target_number>")
        sys.exit(1)

    video_path = sys.argv[1]
    target_number = int(sys.argv[2])

    print(f"[BENCHMARK] Iniciando análise: vídeo={video_path}, alvo=#{target_number}")

    report = run_benchmark(video_path, target_number)

    report_path = Path(__file__).parent / "benchmark_report.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print_summary(report)
    print(f"[BENCHMARK] Relatório salvo em: {report_path}")
