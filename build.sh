#!/usr/bin/env bash
# Builds both sides. Windows (Git Bash, LLVM clang against the MSVC runtime) is the measured machine; macOS only
# smoke-tests the logic.
#   C++: clang++ -O2 (a typical release build) for every program, plus blur at -O3 -march=native (the tuned build).
#        zlib 1.3.2 from source, the version the JDK 25 bundles (bin/zip.dll says "deflate 1.3.2").
#   Java: javac --release 25, one jar.
set -euo pipefail
cd "$(dirname "$0")"
ZLIB_VERSION=1.3.2
ZLIB_SHA256=${ZLIB_SHA256:-}
case "$(uname -s)" in
  MINGW*|MSYS*) EXE=.exe; CXX=${CXX:-"/c/Program Files/LLVM/bin/clang++.exe"}; CC=${CC:-"/c/Program Files/LLVM/bin/clang.exe"}
                JAVA_HOME=${JAVA_HOME:-"/c/Program Files/Eclipse Adoptium/jdk-25.0.5.8-hotspot"};;
  *) EXE=; CXX=${CXX:-clang++}; CC=${CC:-clang}; JAVA_HOME=${JAVA_HOME:-/opt/homebrew/opt/openjdk};;
esac
mkdir -p build third_party java/out

zdir=third_party/zlib-$ZLIB_VERSION
if [[ ! -d $zdir ]]; then
  curl -fsSL -o third_party/zlib.tar.gz "https://github.com/madler/zlib/releases/download/v$ZLIB_VERSION/zlib-$ZLIB_VERSION.tar.gz"
  [[ -z $ZLIB_SHA256 ]] || echo "$ZLIB_SHA256  third_party/zlib.tar.gz" | sha256sum -c -
  tar -xzf third_party/zlib.tar.gz -C third_party
fi
zobjs=()
for c in adler32 compress crc32 deflate inffast inflate inftrees trees uncompr zutil; do
  "$CC" -O2 -D_CRT_SECURE_NO_WARNINGS -c "$zdir/$c.c" -o "build/z_$c.o"
  zobjs+=("build/z_$c.o")
done

CXXFLAGS=(-std=c++20 -Wall -Wextra -D_CRT_SECURE_NO_WARNINGS)
"$CXX" "${CXXFLAGS[@]}" -O2 cpp/hello.cpp -o "build/hello$EXE"
"$CXX" "${CXXFLAGS[@]}" -O2 -I"$zdir" cpp/gzip.cpp "${zobjs[@]}" -o "build/gzip$EXE"
"$CXX" "${CXXFLAGS[@]}" -O2 cpp/blur.cpp -o "build/blur_o2$EXE"
"$CXX" "${CXXFLAGS[@]}" -O3 -march=native cpp/blur.cpp -o "build/blur_native$EXE"
"$CXX" "${CXXFLAGS[@]}" -O2 cpp/trees.cpp -o "build/trees$EXE"

"$JAVA_HOME/bin/javac" --release 25 -d java/out java/src/*.java
"$JAVA_HOME/bin/jar" --create --file java/bench.jar -C java/out .

"build/gzip$EXE" --version
echo built
