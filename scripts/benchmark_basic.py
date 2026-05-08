"""Lightweight benchmark for Coryl's default path."""

from __future__ import annotations

import argparse
import os
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from coryl import Coryl


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--import-runs",
        type=int,
        default=5,
        help="Number of fresh Python processes used to benchmark 'import coryl'.",
    )
    parser.add_argument(
        "--iterations",
        type=int,
        default=100,
        help="Number of in-process iterations for the filesystem operations.",
    )
    args = parser.parse_args()

    results = [
        ("import coryl", _bench_import(args.import_runs)),
        ("create Coryl(root='.')", _bench_create(args.iterations)),
        ("register 10 resources", _bench_register_resources(args.iterations)),
        ("json config write+read", _bench_json_config(args.iterations)),
        ("cache remember_json", _bench_cache_remember_json(args.iterations)),
    ]

    print(f"{'Benchmark':<24} {'avg ms':>10} {'min ms':>10} {'runs':>8}")
    print("-" * 56)
    for name, samples in results:
        print(
            f"{name:<24} {_to_ms(statistics.fmean(samples)):>10.3f} "
            f"{_to_ms(min(samples)):>10.3f} {len(samples):>8}"
        )
    return 0


def _bench_import(runs: int) -> list[float]:
    code = (
        "import os, sys, time; "
        "src = os.environ['CORYL_BENCH_SRC']; "
        "sys.path.insert(0, src); "
        "start = time.perf_counter(); "
        "import coryl; "
        "print(time.perf_counter() - start)"
    )
    env = os.environ.copy()
    env["CORYL_BENCH_SRC"] = str(SRC_ROOT)
    samples: list[float] = []
    for _ in range(runs):
        completed = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            check=True,
            env=env,
            text=True,
        )
        samples.append(float(completed.stdout.strip()))
    return samples


def _bench_create(iterations: int) -> list[float]:
    with tempfile.TemporaryDirectory() as temp_dir:
        previous_cwd = Path.cwd()
        os.chdir(temp_dir)
        try:
            samples: list[float] = []
            for _ in range(iterations):
                start = time.perf_counter()
                Coryl(root=".")
                samples.append(time.perf_counter() - start)
            return samples
        finally:
            os.chdir(previous_cwd)


def _bench_register_resources(iterations: int) -> list[float]:
    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        samples: list[float] = []
        for index in range(iterations):
            workspace = root / f"register-{index}"
            workspace.mkdir()
            start = time.perf_counter()
            app = Coryl(root=workspace)
            for resource_index in range(10):
                app.register_file(
                    f"resource_{resource_index}",
                    f"data/resource_{resource_index}.json",
                )
            samples.append(time.perf_counter() - start)
        return samples


def _bench_json_config(iterations: int) -> list[float]:
    payload = {"debug": True, "name": "coryl", "port": 5432}
    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        samples: list[float] = []
        for index in range(iterations):
            workspace = root / f"config-{index}"
            workspace.mkdir()
            app = Coryl(root=workspace)
            settings = app.configs.add("settings", "config/settings.json")
            start = time.perf_counter()
            settings.save(payload)
            loaded = settings.load()
            samples.append(time.perf_counter() - start)
            if loaded != payload:
                raise AssertionError(
                    "JSON config benchmark payload did not round-trip."
                )
        return samples


def _bench_cache_remember_json(iterations: int) -> list[float]:
    payload = {"id": 42, "name": "Ada"}
    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        samples: list[float] = []
        for index in range(iterations):
            workspace = root / f"cache-{index}"
            workspace.mkdir()
            app = Coryl(root=workspace)
            cache = app.caches.add("api", ".cache/api")
            start = time.perf_counter()
            first = cache.remember_json("users/42.json", lambda: payload, ttl=60)
            second = cache.remember_json("users/42.json", lambda: {"id": 0}, ttl=60)
            samples.append(time.perf_counter() - start)
            if first != payload or second != payload:
                raise AssertionError("Cache benchmark payload did not round-trip.")
        return samples


def _to_ms(seconds: float) -> float:
    return seconds * 1000.0


if __name__ == "__main__":
    raise SystemExit(main())
