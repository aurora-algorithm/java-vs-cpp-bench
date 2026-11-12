#pragma once
// Seconds since this process was created, and the optional progress log the race charts are drawn from.
// Java's side uses ProcessHandle's start instant, so both lines start at the moment Windows created the process.
#include <chrono>
#include <cstdio>
#include <cstdlib>

#ifdef _WIN32
#define WIN32_LEAN_AND_MEAN
#define NOMINMAX
#include <windows.h>

inline double since_start() {
  FILETIME created, exited, kernel, user, now;
  GetProcessTimes(GetCurrentProcess(), &created, &exited, &kernel, &user);
  GetSystemTimePreciseAsFileTime(&now);
  auto ticks = [](FILETIME t) { return (static_cast<unsigned long long>(t.dwHighDateTime) << 32) | t.dwLowDateTime; };
  return static_cast<double>(ticks(now) - ticks(created)) / 1e7;
}
#else
// Smoke tests on other systems only: time from the first call, which misses the loader's share.
inline double since_start() {
  static const auto t0 = std::chrono::steady_clock::now();
  return std::chrono::duration<double>(std::chrono::steady_clock::now() - t0).count();
}
#endif

/** Appends "units<TAB>seconds" lines to $PROGRESS_OUT when it is set; a no-op in timed runs. */
class Progress {
 public:
  Progress() {
    const char* path = std::getenv("PROGRESS_OUT");
    if (path) f_ = std::fopen(path, "w");
  }
  ~Progress() {
    if (f_) std::fclose(f_);
  }
  Progress(const Progress&) = delete;
  Progress& operator=(const Progress&) = delete;
  bool on() const { return f_ != nullptr; }
  void mark(long long units) {
    if (f_) std::fprintf(f_, "%lld\t%.6f\n", units, since_start());
  }

 private:
  std::FILE* f_ = nullptr;
};
