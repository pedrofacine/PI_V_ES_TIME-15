#!/usr/bin/env python
"""
Orquestrador de testes SmartScout.

Uso:
    python run_all_tests.py                              # unit + integration + lint
    python run_all_tests.py --benchmark video.mp4 10    # + benchmark

Gera:
    reports/test_report.html
    reports/coverage/index.html  (se pytest-cov instalado)
    benchmark/benchmark_report.json  (se --benchmark usado)
"""
import sys
import subprocess
import argparse
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
FRONTEND_DIR = PROJECT_ROOT / "frontend"
REPORTS_DIR = PROJECT_ROOT / "reports"
REPORTS_DIR.mkdir(exist_ok=True)


def run(cmd: list[str], cwd=None) -> tuple[int, str, str]:
    result = subprocess.run(cmd, cwd=cwd or PROJECT_ROOT, capture_output=True, text=True)
    return result.returncode, result.stdout, result.stderr


def step(label: str):
    print(f"\n{'─'*55}")
    print(f"  {label}")
    print(f"{'─'*55}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--benchmark", nargs=2, metavar=("VIDEO_PATH", "TARGET_NUMBER"),
                        help="Run benchmark after tests")
    args = parser.parse_args()

    results = {}

    # ── 1. Pytest (unit + integration) ──────────────────────────
    step("[1/4] pytest — Unit + Integration Tests")
    report_html = REPORTS_DIR / "test_report.html"
    cov_dir = REPORTS_DIR / "coverage"
    pytest_cmd = [
        sys.executable, "-m", "pytest", "tests/",
        f"--html={report_html}",
        "--self-contained-html",
        f"--cov=ml",
        f"--cov=backend/app",
        f"--cov-report=html:{cov_dir}",
        "--cov-report=term-missing:skip-covered",
        "-q",
    ]
    rc, out, err = run(pytest_cmd)
    print(out[-3000:] if len(out) > 3000 else out)
    if err:
        print(err[-500:])

    # Parse pass/fail from pytest output
    pytest_ok = rc == 0
    passed = failed = 0
    for line in out.splitlines():
        if " passed" in line:
            parts = line.strip().split()
            for i, p in enumerate(parts):
                if p == "passed" and i > 0:
                    try:
                        passed = int(parts[i - 1])
                    except ValueError:
                        pass
                if p == "failed" and i > 0:
                    try:
                        failed = int(parts[i - 1])
                    except ValueError:
                        pass

    results["pytest"] = {"ok": pytest_ok, "passed": passed, "failed": failed,
                         "report": str(report_html)}

    # ── 2. Frontend ESLint ───────────────────────────────────────
    step("[2/4] ESLint — Frontend Lint")
    rc_lint, out_lint, err_lint = run(["npm", "run", "lint"], cwd=FRONTEND_DIR)
    lint_ok = rc_lint == 0
    print(out_lint[-1000:] if out_lint else "(sem saída)")
    if err_lint:
        print(err_lint[-300:])
    results["eslint"] = {"ok": lint_ok}

    # ── 3. TypeScript type check ─────────────────────────────────
    step("[3/4] TypeScript — Type Check (tsc --noEmit)")
    rc_tsc, out_tsc, err_tsc = run(
        ["npx", "tsc", "--noEmit"], cwd=FRONTEND_DIR
    )
    tsc_ok = rc_tsc == 0
    print(out_tsc[-1000:] if out_tsc else "(sem erros de tipo)")
    if err_tsc:
        print(err_tsc[-300:])
    results["tsc"] = {"ok": tsc_ok}

    # ── 4. Benchmark (optional) ──────────────────────────────────
    step("[4/4] Benchmark do Modelo de IA")
    if args.benchmark:
        video_path, target_number = args.benchmark
        print(f"  Rodando benchmark: vídeo={video_path}, alvo=#{target_number}")
        rc_bm, out_bm, err_bm = run(
            [sys.executable, "benchmark/benchmark_model.py", video_path, target_number]
        )
        bm_ok = rc_bm == 0
        print(out_bm[-2000:] if out_bm else "")
        if err_bm:
            print(err_bm[-500:])
        results["benchmark"] = {
            "ok": bm_ok,
            "report": str(PROJECT_ROOT / "benchmark" / "benchmark_report.json")
        }
    else:
        print("  (Pulado — use --benchmark <video.mp4> <número> para rodar)")
        results["benchmark"] = {"ok": None, "report": None}

    # ── Sumário Final ────────────────────────────────────────────
    print("\n")
    print("╔" + "═" * 53 + "╗")
    print("║" + "     SMARTSCOUT — RELATÓRIO FINAL DE TESTES".center(53) + "║")
    print("╠" + "═" * 53 + "╣")

    p = results["pytest"]
    p_status = "OK" if p["ok"] else "FALHOU"
    print(f"║  Unit + Integration   | {p['passed']} passed, {p['failed']} failed | {p_status}".ljust(54) + "║")

    def status(ok):
        return "OK" if ok else ("FALHOU" if ok is False else "Pulado")

    print(f"║  Frontend Lint        | {status(results['eslint']['ok'])}".ljust(54) + "║")
    print(f"║  Frontend Types       | {status(results['tsc']['ok'])}".ljust(54) + "║")
    bm = results["benchmark"]
    bm_label = f"Relatorio: {bm['report']}" if bm["ok"] is not None else "Nao executado"
    print(f"║  Benchmark (IA)       | {status(bm['ok'])} — {bm_label[:30]}".ljust(54) + "║")
    print("╚" + "═" * 53 + "╝")

    if p["report"]:
        print(f"\n  Relatorio HTML:  {p['report']}")
    cov_index = REPORTS_DIR / "coverage" / "index.html"
    if cov_index.exists():
        print(f"  Cobertura:       {cov_index}")

    all_ok = p["ok"] and lint_ok and tsc_ok
    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
