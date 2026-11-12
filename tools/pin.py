#!/usr/bin/env python3
"""Runs a command pinned to a set of logical CPUs; on Windows the command's own children inherit the mask.

usage: python pin.py CPU[,CPU...] COMMAND...
"""
import subprocess
import sys

import psutil


def main() -> int:
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    psutil.Process().cpu_affinity([int(c) for c in sys.argv[1].split(",")])
    return subprocess.call(sys.argv[2:])


if __name__ == "__main__":
    sys.exit(main())
