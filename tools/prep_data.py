#!/usr/bin/env python3
"""Builds the inputs both sides read, deterministically, and prints their sha256.

usage: python3 -I tools/prep_data.py photos JPEG_DIR      -> data/photos/NN.rgb (Pillow; run on the Mac)
       python3 -I tools/prep_data.py corpus SRC_ZIP       -> data/corpus.tar (the JDK's own source code, src.zip)

.rgb = 8-byte header (width, height as little-endian u32) + the decoded RGB pixels.
corpus.tar = every file of src.zip in name order, mtime 0, owner 0, mode 0644, so it is the same bytes everywhere.
"""
import hashlib
import io
import struct
import sys
import tarfile
import zipfile
from pathlib import Path

DATA = Path(__file__).resolve().parents[1] / "data"


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 24), b""):
            h.update(block)
    return h.hexdigest()


def photos(src: Path) -> None:
    from PIL import Image  # noqa: PLC0415 (Mac only)

    out = DATA / "photos"
    out.mkdir(parents=True, exist_ok=True)
    for i, jpg in enumerate(sorted(src.glob("*.jpg")), 1):
        img = Image.open(jpg).convert("RGB")
        dst = out / f"{i:02d}.rgb"
        with open(dst, "wb") as f:
            f.write(struct.pack("<II", *img.size))
            f.write(img.tobytes())
        print(f"{dst.name} {img.size[0]}x{img.size[1]} {jpg.name} {sha(dst)}")


def corpus(src: Path) -> None:
    dst = DATA / "corpus.tar"
    files = 0
    with zipfile.ZipFile(src) as z, tarfile.open(dst, "w", format=tarfile.USTAR_FORMAT) as tar:
        for name in sorted(n for n in z.namelist() if not n.endswith("/")):
            body = z.read(name)
            info = tarfile.TarInfo(name)
            info.size, info.mtime, info.mode, info.uid, info.gid = len(body), 0, 0o644, 0, 0
            tar.addfile(info, io.BytesIO(body))
            files += 1
    print(f"{dst.name} {files} files {dst.stat().st_size} bytes {sha(dst)}")


if __name__ == "__main__":
    if len(sys.argv) != 3 or sys.argv[1] not in ("photos", "corpus"):
        sys.exit(__doc__)
    {"photos": photos, "corpus": corpus}[sys.argv[1]](Path(sys.argv[2]))
