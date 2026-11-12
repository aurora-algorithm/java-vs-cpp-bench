#!/usr/bin/env python3
"""The measurement session, natively on Windows (i7-13700F): is Java really slower than C++?

Every cell runs under hyperfine (1 warm-up, then N runs, no shell), pinned to the same two performance cores for both
languages, inside a pseudo-console so the live screen is recorded as a cast. hyperfine times the whole process, so a
Java run includes starting the JVM and the JIT warming up. Rounds alternate which language goes first. After each
cell of tests 1-3, one more run logs its own progress (seconds since the OS created the process) for the race
charts. A final round runs without the recorder, to check that recording didn't move the numbers. Every output is
hashed: the two languages must write the same bytes.

usage: python tools/session.py RESULTS_DIR [ROUNDS=5]      (from the repo root, on Windows)
env:   BENCH_PILOT=1    small run counts (pilot)       BENCH_NO_GATE=1   skip the quiet gate (pilot only)
"""

import hashlib
import json
import os
import platform
import re
import subprocess
import sys
import time
from pathlib import Path

import psutil

# Two performance cores on different physical cores (EfficiencyClass 1); their SMT siblings 5 and 7 stay idle, and
# the quiet gate watches all four. C++ runs on one thread; the JVM's JIT and GC threads may use the second core.
PINNED = [4, 6]
GATE_CPUS = [4, 5, 6, 7]
HYPERFINE = os.environ.get(
    "HYPERFINE", str(Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft/WinGet/Links/hyperfine.exe")
)
JAVA = os.environ.get("JAVA", "C:/Program Files/Eclipse Adoptium/jdk-25.0.5.8-hotspot/bin/java.exe")
ZIP_DLL = Path(JAVA).with_name("zip.dll")
CLANG = os.environ.get("CLANG", r"C:\Program Files\LLVM\bin\clang++.exe")
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
PY = str(Path(sys.executable).with_name("python.exe"))
PILOT = os.environ.get("BENCH_PILOT") == "1"
COLS, ROWS = 52, 4  # hyperfine's progress line and final stats fit; text stays big on a phone

B = "build"
JAR = "java/bench.jar"
CORPUS = "data/corpus.tar"
PHOTOS = "data/photos"
RADIUS = "12"
DEPTH = os.environ.get("BENCH_DEPTH", "20")
RUNS = {0: 30, 1: 10, 2: 10, 3: 10} if not PILOT else {0: 10, 1: 3, 2: 3, 3: 3}


def java(*args: str, flags: tuple[str, ...] = ()) -> list[str]:
    return [JAVA, *flags, "-cp", JAR, *args]


# (cell, test, side, label shown by hyperfine, argv); {out} is a file or folder inside the round's directory
CELLS = [
    ("cpp-hello", 0, "cpp", "C++ hello", [f"{B}/hello.exe"]),
    ("java-hello", 0, "java", "Java hello", java("Hello")),
    ("cpp-gzip", 1, "cpp", "C++ zlib", [f"{B}/gzip.exe", CORPUS, "{out}"]),
    ("java-gzip", 1, "java", "Java java.util.zip", java("Gzip", CORPUS, "{out}")),
    ("cpp-blur", 2, "cpp", "C++ clang -O2", [f"{B}/blur_o2.exe", PHOTOS, "{out}", RADIUS]),
    ("cpp-blur-native", 2, "cpp", "C++ -O3 -march=native", [f"{B}/blur_native.exe", PHOTOS, "{out}", RADIUS]),
    ("java-blur", 2, "java", "Java", java("Blur", PHOTOS, "{out}", RADIUS)),
    ("cpp-trees", 3, "cpp", "C++ make_unique", [f"{B}/trees.exe", DEPTH, "{out}", "unique"]),
    ("cpp-trees-arena", 3, "cpp", "C++ arena (pmr)", [f"{B}/trees.exe", DEPTH, "{out}", "arena"]),
    ("java-trees", 3, "java", "Java new, G1 GC", java("Trees", DEPTH, "{out}")),
]
# Evidence for the "why": does the JIT vectorize the blur loops? Same time with SuperWord off means it doesn't.
CELLS.append(
    (
        "java-blur-nosuperword",
        2,
        "java",
        "Java, SuperWord off",
        java("Blur", PHOTOS, "{out}", RADIUS, flags=("-XX:-UseSuperWord",)),
    )
)
OUTPUT_TESTS = {1, 2, 3}
PROGRESS_TESTS = {1, 2, 3}


def log(msg: str) -> None:
    print(time.strftime("%H:%M:%S"), msg, flush=True)


def quiet_gate(max_wait: int = 1800) -> dict:
    """Waits until the session's cores are idle (mean under 5%, none over 15%, over 5 s) and the whole machine is under
    20%; returns that reading. Gives up after max_wait: a busy machine (a game, a render, another bench) voids the
    numbers, so the session never measures through it."""
    if os.environ.get("BENCH_NO_GATE") == "1":
        return {"gate": "skipped"}
    waited = 0
    while True:
        per = psutil.cpu_percent(interval=5, percpu=True)
        cores = [per[c] for c in GATE_CPUS]
        reading = {"cores": cores, "mean": sum(cores) / len(cores), "total": sum(per) / len(per)}
        if reading["mean"] < 5 and max(cores) < 15 and reading["total"] < 20:
            return reading
        if waited >= max_wait:
            raise RuntimeError(f"machine stayed busy for {max_wait} s: {reading}")
        if waited % 300 == 0:
            log(f"machine busy {reading}, waiting")
        waited += 5


def pinned(argv: list[str]) -> list[str]:
    return [PY, str(Path(__file__).with_name("pin.py")), ",".join(map(str, PINNED)), *argv]


def hyperfine(label: str, argv: list[str], export: Path, runs: int) -> list[str]:
    cmd = subprocess.list2cmdline(argv)
    return [HYPERFINE, "-N", "--warmup", "1", "--runs", str(runs), "-n", label, "--export-json", str(export), cmd]


def measurements(report: dict) -> list[dict]:
    """Every run of a hyperfine 2.x export (schema_version 2): wall, user and system seconds, peak memory if reported."""
    out = []
    for m in report["results"][0]["measurements"]:
        if m["exit_code"] != 0 or m["time_wall_clock"]["unit"] != "second":
            raise RuntimeError(f"unexpected measurement {m}")
        out.append(m)
    return out


def order_for(round_no: int) -> list[tuple]:
    """Each test's cells, C++ first in odd rounds and Java first in even ones."""
    first = "cpp" if round_no % 2 == 1 else "java"
    cells = []
    for test in sorted({c[1] for c in CELLS}):
        cells += sorted((c for c in CELLS if c[1] == test), key=lambda c: c[2] != first)
    return cells


def digest(path: Path) -> str:
    h = hashlib.sha256()
    files = sorted(path.iterdir()) if path.is_dir() else [path]
    for f in files:
        with open(f, "rb") as src:
            for block in iter(lambda: src.read(1 << 24), b""):
                h.update(block)
    return h.hexdigest()


def run_cell(cell: tuple, rdir: Path, record: bool) -> dict:
    name, test, side, label, argv = cell
    out = rdir / f"out-{name}"
    # Forward slashes: hyperfine -N splits the command like a POSIX shell, where a backslash is an escape.
    real = [a.replace("{out}", out.as_posix()) for a in argv]
    export = rdir / f"{name}.json"
    hf = pinned(hyperfine(label, real, export, RUNS[test]))
    busy = quiet_gate()
    t0 = time.time()
    if record:
        cast = rdir / f"{name}.cast"
        rc = subprocess.call(
            [PY, str(Path(__file__).with_name("cast.py")), str(cast), str(COLS), str(ROWS), "--", *hf],
            creationflags=NO_WINDOW,
        )
    else:
        rc = subprocess.call(hf, stdout=subprocess.DEVNULL, creationflags=NO_WINDOW)
    if rc != 0 or not export.exists():
        raise RuntimeError(f"{name}: hyperfine failed ({rc})")
    ms = measurements(json.loads(export.read_text()))
    result = {
        "cell": name,
        "test": test,
        "side": side,
        "label": label,
        "argv": real,
        "runs_s": [m["time_wall_clock"]["value"] for m in ms],
        "measurements": ms,
        "busy_before": busy,
        "busy_after": quiet_reading(),
        "started": t0,
        "ended": time.time(),
        "sha256": digest(out) if test in OUTPUT_TESTS else None,
        "out_bytes": size_of(out) if test in OUTPUT_TESTS else None,
    }
    if record and test in PROGRESS_TESTS:
        env = dict(os.environ, PROGRESS_OUT=str(rdir / f"{name}.progress.tsv"))
        subprocess.check_call(pinned(real), env=env, stdout=subprocess.DEVNULL, creationflags=NO_WINDOW)
    remove(out)
    return result


def size_of(path: Path) -> int:
    return sum(f.stat().st_size for f in path.iterdir()) if path.is_dir() else path.stat().st_size


def quiet_reading() -> dict:
    per = psutil.cpu_percent(interval=1, percpu=True)
    return {"cores": [per[c] for c in GATE_CPUS], "total": sum(per) / len(per)}


def remove(path: Path) -> None:
    if path.is_dir():
        for f in path.iterdir():
            f.unlink()
        path.rmdir()
    elif path.exists():
        path.unlink()


def versions() -> dict:
    def cmd(*a: str) -> str:
        p = subprocess.run(a, check=False, capture_output=True, text=True, creationflags=NO_WINDOW)
        return (p.stdout + p.stderr).strip()

    dll = ZIP_DLL.read_bytes()
    return {
        "java": cmd(JAVA, "-version"),
        "jvm_on_pinned_cores": cmd(*pinned(java("Hello", "info"))),
        "jdk_zlib": sorted({m.decode() for m in re.findall(rb"deflate (\d+\.\d+\.\d+)", dll)}),
        "cpp_zlib": cmd(f"{B}/gzip.exe", "--version"),
        "clang": cmd(CLANG, "--version").splitlines()[0],
        "hyperfine": cmd(HYPERFINE, "--version"),
        "os": platform.platform(),
        "cpu": platform.processor(),
        "ram_bytes": psutil.virtual_memory().total,
        "power_plan": cmd("powercfg", "/getactivescheme"),
    }


def inputs() -> dict:
    photos = sorted(Path(PHOTOS).glob("*.rgb"))
    return {
        "corpus": {"path": CORPUS, "bytes": Path(CORPUS).stat().st_size, "sha256": digest(Path(CORPUS))},
        "photos": [{"name": p.name, "bytes": p.stat().st_size, "sha256": digest(p)} for p in photos],
        "radius": int(RADIUS),
        "depth": int(DEPTH),
    }


def main() -> int:
    results = Path(sys.argv[1])
    rounds = int(sys.argv[2]) if len(sys.argv) > 2 else 5
    results.mkdir(parents=True, exist_ok=False)
    (results / "meta.json").write_text(
        json.dumps(
            {
                "versions": versions(),
                "inputs": inputs(),
                "rounds": rounds,
                "pinned_cpus": PINNED,
                "gate_cpus": GATE_CPUS,
                "runs_per_cell": RUNS,
                "pilot": PILOT,
                "started": time.ctime(),
            },
            indent=2,
        )
    )
    log("waiting for a quiet machine (up to 30 min)")
    quiet_gate(max_wait=1800)
    all_runs = []
    for r in range(1, rounds + 2):
        record = r <= rounds
        rdir = results / (f"round{r}" if record else "plain")
        rdir.mkdir()
        log(f"round {r} ({'recorded' if record else 'plain'})")
        for cell in order_for(r):
            res = run_cell(cell, rdir, record)
            res["round"] = r if record else "plain"
            all_runs.append(res)
            med = sorted(res["runs_s"])[len(res["runs_s"]) // 2]
            log(f"  {res['cell']:24s} median {med:.3f} s")
            with open(results / "runs.jsonl", "a") as f:
                f.write(json.dumps(res) + "\n")
        for test in OUTPUT_TESTS:
            shas = {x["sha256"] for x in all_runs if x["test"] == test}
            if len(shas) != 1:
                raise RuntimeError(f"test {test}: outputs differ ({shas})")
    log("done")
    return 0


if __name__ == "__main__":
    sys.exit(main())
