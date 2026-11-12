// Test 1: gzip one file with zlib, the library Java's java.util.zip calls too.
// usage: gzip IN OUT        gzip --version prints the zlib version it was built with
#include <zlib.h>

#include <cstdio>
#include <cstring>
#include <vector>

#include "clock.hpp"

constexpr size_t kChunk = 64 * 1024;
constexpr long long kProgressEvery = 8LL << 20;

int main(int argc, char** argv) {
  if (argc == 2 && std::strcmp(argv[1], "--version") == 0) {
    std::printf("zlib %s\n", zlibVersion());
    return 0;
  }
  if (argc != 3) {
    std::fprintf(stderr, "usage: gzip IN OUT\n");
    return 2;
  }
  std::FILE* in = std::fopen(argv[1], "rb");
  std::FILE* out = std::fopen(argv[2], "wb");
  if (!in || !out) {
    std::fprintf(stderr, "cannot open %s or %s\n", argv[1], argv[2]);
    return 1;
  }
  z_stream z{};
  // windowBits 15 + 16 = a gzip wrapper, the same format and level as Java's GZIPOutputStream.
  if (deflateInit2(&z, Z_DEFAULT_COMPRESSION, Z_DEFLATED, 15 + 16, 8, Z_DEFAULT_STRATEGY) != Z_OK) return 1;
  // GZIPOutputStream writes mtime 0 and OS 255 ("unknown"); same header here, so the outputs can be compared byte for byte.
  gz_header header{};
  header.os = 255;
  deflateSetHeader(&z, &header);

  std::vector<unsigned char> src(kChunk), dst(kChunk);
  Progress progress;
  long long done = 0, next = kProgressEvery;
  int flush = Z_NO_FLUSH;
  do {
    size_t n = std::fread(src.data(), 1, kChunk, in);
    if (std::ferror(in)) return 1;
    flush = std::feof(in) ? Z_FINISH : Z_NO_FLUSH;
    z.next_in = src.data();
    z.avail_in = static_cast<uInt>(n);
    do {
      z.next_out = dst.data();
      z.avail_out = static_cast<uInt>(kChunk);
      if (deflate(&z, flush) == Z_STREAM_ERROR) return 1;
      std::fwrite(dst.data(), 1, kChunk - z.avail_out, out);
    } while (z.avail_out == 0);
    done += static_cast<long long>(n);
    if (progress.on() && done >= next) {
      progress.mark(done);
      next += kProgressEvery;
    }
  } while (flush != Z_FINISH);
  progress.mark(done);
  deflateEnd(&z);
  std::fclose(in);
  return std::fclose(out) == 0 ? 0 : 1;
}
