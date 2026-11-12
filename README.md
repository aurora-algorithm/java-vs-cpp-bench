# Java vs C++: gzip, image blur and binary trees

Code and per-run results behind the "Is Java slower than C++? C++ wins two tests, Java wins one by 6x" Short.

## What is tested
Three jobs, written the same way in both languages, plus the cost of starting a program:

| Test | Job | C++ | Java | Output check |
|---|---|---|---|---|
| 0 | start and exit (`hello`) | clang `-O2` | `java -cp bench.jar Hello` | none |
| 1 | gzip a 223 MB tar of the JDK 25 source code (15,066 files) | zlib 1.3.2, level 6 | `java.util.zip.GZIPOutputStream` (the JDK's bundled zlib 1.3.2) | byte-identical `.gz` |
| 2 | box-blur 4 photos (28 to 38 megapixels, radius 12) and save them | clang `-O2`, and `-O3 -march=native` | stock JIT; also run with `-XX:-UseSuperWord` | byte-identical output |
| 3 | build and walk binary trees (Benchmarks Game "binary-trees", depth 20, one thread) | `std::make_unique` per node, and one preallocated arena block, rewound per tree (a hand-written bump allocator) | `new Node`, G1 (the default GC) | identical text |

The blur and tree loops are the same in both languages (`cpp/blur.cpp` vs `java/src/Blur.java`, `cpp/trees.cpp` vs
`java/src/Trees.java`) and use integer maths only, so the outputs can be compared byte for byte. The
`-XX:-UseSuperWord` run turns off the JIT's loop vectorizer, to check whether the JIT vectorized the blur loop.

## Setup
From `results/java-vs-cpp-i7-20261109-2137/meta.json`:
- **Machine:** Intel i7-13700F PC, 32 GB, native Windows 11 (build 26200), Balanced power plan. No Docker, no VM.
- **Versions:** Eclipse Temurin 25.0.5 (HotSpot) · clang 23.1.5 against the MSVC runtime · zlib 1.3.2 · hyperfine 2.0.0.
- **Pinning:** both languages run on the same two performance cores (logical CPUs 4 and 6). The C++ programs use one
  thread. The JVM also runs its JIT and GC threads, which may use the second core.
- **Timing:** hyperfine times the whole process (1 warm-up, then 10 runs per cell, 30 for startup), so every Java
  number includes starting the JVM and the JIT warming up.
- **Runs:** 5 recorded rounds (the hyperfine screen was captured as an asciinema cast) plus 1 plain round without the
  recorder, to check the recorder did not move the numbers. Rounds alternate which language goes first.
- **Quiet machine:** before every cell the script waits until the pinned cores and their SMT siblings average under
  5% CPU (none over 15%) and the whole machine is under 20%.
- **Output check:** every output is hashed after every cell; the session stops if the two languages ever write
  different bytes.

## Results
Median of every recorded run (5 rounds x 10 runs, 5 x 30 for startup), from
`results/java-vs-cpp-i7-20261109-2137/summary.json` (made by `tools/summary.py` from `runs.jsonl`).

| Test | Config | Median | Min to max | Plain round |
|---|---|---|---|---|
| 0 start | C++ `hello` | 2.8 ms | 2.6 to 4.6 ms | 3.4 ms |
| 0 start | Java `Hello` | 37.5 ms | 34.9 to 59.0 ms | 37.9 ms |
| 1 gzip | C++ zlib | 3.21 s | 3.15 to 3.37 s | 3.23 s |
| 1 gzip | Java `java.util.zip` | 3.57 s | 3.51 to 4.10 s | 3.56 s |
| 2 blur | C++ clang `-O2` | 2.33 s | 2.29 to 2.45 s | 2.34 s |
| 2 blur | C++ `-O3 -march=native` | 1.91 s | 1.87 to 2.01 s | 1.94 s |
| 2 blur | Java, stock JIT | 6.55 s | 6.25 to 7.13 s | 6.54 s |
| 2 blur | Java, `-XX:-UseSuperWord` | 6.56 s | 6.25 to 6.89 s | 6.60 s |
| 3 trees | C++ `make_unique` | 8.46 s | 8.17 to 8.86 s | 8.42 s |
| 3 trees | C++ arena (hyperfine label "C++ arena (pmr)") | 0.97 s | 0.94 to 1.01 s | 0.96 s |
| 3 trees | Java `new`, G1 | 1.34 s | 1.30 to 1.43 s | 1.33 s |

Every run, with hyperfine's user/system time and the quiet-gate readings, is in `runs.jsonl`. Each round folder holds
the hyperfine exports (`*.json`), the screen casts (`*.cast`) and one progress log per cell (`*.progress.tsv`,
seconds since the OS created the process, per unit of work).

## Reproduce
Needs Windows with Git Bash, LLVM clang, a JDK 25, hyperfine, and Python 3 with `psutil` and `pywinpty`.
`build.sh` also works on macOS for a quick check of the logic.

```bash
# inputs (not in the repo: about 640 MB)
# 1. the JDK 25's lib/src.zip
python3 -I tools/prep_data.py corpus "$JAVA_HOME/lib/src.zip"
# 2. download the four photos listed in data/PHOTOS.md as photo1.jpg .. photo4.jpg into one folder (needs Pillow)
python3 -I tools/prep_data.py photos path/to/jpegs

./build.sh                                          # downloads and builds zlib 1.3.2, then both sides
python tools/session.py results/my-session 5        # BENCH_PILOT=1 for a short pilot
python tools/summary.py results/my-session
```

`session.py` looks for hyperfine, java and clang at their default Windows install paths; set `HYPERFINE`, `JAVA` or
`CLANG` to point elsewhere. Change `PINNED` and `GATE_CPUS` at the top of the script to match your CPU's core layout.
`prep_data.py` prints the sha256 of each input; compare them with `meta.json`.

## Settings people may argue about
- Every JVM setting is as it ships: stock JIT, G1, default heap. The Vector API is not used.
- C++ is built at `-O2`, a common release level. The `-O3 -march=native` blur build is shown next to it.
- The `make_unique` trees use the default Windows heap (the MSVC runtime's `new`). No other allocator was tried.
- With the stock JIT the blur loop takes the same time with `-XX:-UseSuperWord` (6.56 s vs 6.55 s), so the JIT left
  it scalar. clang vectorizes the same loop.
- hyperfine times the whole process, so Java's numbers include JVM startup and JIT warm-up.
- The JVM may use the second pinned core for JIT and GC threads; the C++ programs use one.

## License
MIT, see `LICENSE`. The photos are not included; their authors and licenses are listed in `data/PHOTOS.md`.
