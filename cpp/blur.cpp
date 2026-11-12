// Test 2: box-blur every photo in a folder (raw RGB, 8-byte header: width, height as little-endian u32).
// usage: blur IN_DIR OUT_DIR RADIUS
// Same loops as java/src/Blur.java, integer maths only, so both write the same bytes.
#include <algorithm>
#include <cstdint>
#include <cstdio>
#include <filesystem>
#include <fstream>
#include <string>
#include <vector>

#include "clock.hpp"

namespace fs = std::filesystem;

static void blur(const uint8_t* src, uint8_t* tmp, uint8_t* dst, int w, int h, int r) {
  const int w3 = w * 3;
  const int d = 2 * r + 1;
  const int32_t m = (65536 + d / 2) / d;  // fixed-point 1/d
  std::vector<int32_t> acc(w3);
  // Vertical pass: each output row is the average of the 2r+1 rows around it (edges repeat).
  for (int y = 0; y < h; y++) {
    std::fill(acc.begin(), acc.end(), 0);
    for (int k = -r; k <= r; k++) {
      const uint8_t* row = src + static_cast<size_t>(std::clamp(y + k, 0, h - 1)) * w3;
      for (int i = 0; i < w3; i++) acc[i] += row[i];
    }
    uint8_t* o = tmp + static_cast<size_t>(y) * w3;
    for (int i = 0; i < w3; i++) o[i] = static_cast<uint8_t>((acc[i] * m + 32768) >> 16);
  }
  // Horizontal pass on a copy of the row padded with its edge pixels.
  std::vector<uint8_t> pad(static_cast<size_t>(w + 2 * r) * 3);
  for (int y = 0; y < h; y++) {
    const uint8_t* row = tmp + static_cast<size_t>(y) * w3;
    for (int x = 0; x < r; x++) {
      std::copy(row, row + 3, pad.data() + x * 3);
      std::copy(row + w3 - 3, row + w3, pad.data() + (r + w + x) * 3);
    }
    std::copy(row, row + w3, pad.data() + r * 3);
    std::fill(acc.begin(), acc.end(), 0);
    for (int k = 0; k < d; k++) {
      const uint8_t* p = pad.data() + k * 3;
      for (int i = 0; i < w3; i++) acc[i] += p[i];
    }
    uint8_t* o = dst + static_cast<size_t>(y) * w3;
    for (int i = 0; i < w3; i++) o[i] = static_cast<uint8_t>((acc[i] * m + 32768) >> 16);
  }
}

static uint32_t le32(const unsigned char* b) { return b[0] | b[1] << 8 | b[2] << 16 | static_cast<uint32_t>(b[3]) << 24; }

int main(int argc, char** argv) {
  if (argc != 4) {
    std::fprintf(stderr, "usage: blur IN_DIR OUT_DIR RADIUS\n");
    return 2;
  }
  const int r = std::stoi(argv[3]);
  std::vector<fs::path> photos;
  for (const auto& e : fs::directory_iterator(argv[1]))
    if (e.path().extension() == ".rgb") photos.push_back(e.path());
  std::sort(photos.begin(), photos.end());
  if (photos.empty()) {
    std::fprintf(stderr, "no .rgb files in %s\n", argv[1]);
    return 1;
  }
  fs::create_directories(argv[2]);
  Progress progress;
  long long done = 0;
  for (const auto& path : photos) {
    std::ifstream in(path, std::ios::binary);
    unsigned char hdr[8];
    in.read(reinterpret_cast<char*>(hdr), 8);
    const int w = static_cast<int>(le32(hdr)), h = static_cast<int>(le32(hdr + 4));
    const size_t n = static_cast<size_t>(w) * h * 3;
    std::vector<uint8_t> src(n), tmp(n), dst(n);
    in.read(reinterpret_cast<char*>(src.data()), static_cast<std::streamsize>(n));
    if (!in) {
      std::fprintf(stderr, "short read: %s\n", path.string().c_str());
      return 1;
    }
    blur(src.data(), tmp.data(), dst.data(), w, h, r);
    std::ofstream out(fs::path(argv[2]) / path.filename(), std::ios::binary);
    out.write(reinterpret_cast<const char*>(hdr), 8);
    out.write(reinterpret_cast<const char*>(dst.data()), static_cast<std::streamsize>(n));
    if (!out) return 1;
    progress.mark(++done);
  }
  return 0;
}
