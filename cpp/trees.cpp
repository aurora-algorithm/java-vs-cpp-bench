// Test 3: build and walk millions of small binary trees (the Benchmarks Game "binary-trees" job, one thread).
// usage: trees DEPTH OUT unique|arena
//   unique: every node is its own heap allocation (std::make_unique, freed by the destructor), the usual C++
//   arena:  every tree lives in one preallocated block and is dropped by rewinding it (reset)
#include <algorithm>
#include <cstdio>
#include <cstring>
#include <memory>
#include <new>
#include <string>

#include "clock.hpp"

constexpr int kMinDepth = 4;

struct Node {
  std::unique_ptr<Node> left, right;
};

static std::unique_ptr<Node> make(int d) {
  auto n = std::make_unique<Node>();
  if (d > 0) {
    n->left = make(d - 1);
    n->right = make(d - 1);
  }
  return n;
}

static long long check(const Node& n) { return n.left ? 1 + check(*n.left) + check(*n.right) : 1; }

struct ArenaNode {
  ArenaNode* left;
  ArenaNode* right;
};

// One block taken once; a node is the next 16 bytes of it, and reset() rewinds to the start. (MSVC's
// std::pmr::monotonic_buffer_resource did not reuse its initial buffer after release() in the pilot.)
class Arena {
 public:
  explicit Arena(size_t nodes) : block_(std::make_unique<ArenaNode[]>(nodes)), cap_(nodes) {}
  ArenaNode* alloc() {
    if (used_ == cap_) throw std::bad_alloc();
    return &block_[used_++];
  }
  void reset() { used_ = 0; }

 private:
  std::unique_ptr<ArenaNode[]> block_;
  size_t cap_;
  size_t used_ = 0;
};

static ArenaNode* make(int d, Arena& mem) {
  ArenaNode* n = mem.alloc();
  n->left = d > 0 ? make(d - 1, mem) : nullptr;
  n->right = d > 0 ? make(d - 1, mem) : nullptr;
  return n;
}

static long long check(const ArenaNode* n) { return n->left ? 1 + check(n->left) + check(n->right) : 1; }

int main(int argc, char** argv) {
  if (argc != 4 || (std::strcmp(argv[3], "unique") != 0 && std::strcmp(argv[3], "arena") != 0)) {
    std::fprintf(stderr, "usage: trees DEPTH OUT unique|arena\n");
    return 2;
  }
  const int max_depth = std::max(kMinDepth + 2, std::stoi(argv[1]));
  const bool arena = std::strcmp(argv[3], "arena") == 0;
  std::FILE* out = std::fopen(argv[2], "wb");  // binary: "\n" on every OS, like Java's output
  if (!out) return 1;
  Progress progress;
  long long trees = 0;

  // One tree of depth d, built, walked and freed; returns its node count.
  // Big enough for the largest tree (the stretch tree, depth max + 1).
  Arena pool(arena ? (size_t{1} << (max_depth + 2)) : 0);
  auto one = [&](int d) -> long long {
    if (!arena) return check(*make(d));
    long long c = check(make(d, pool));
    pool.reset();
    return c;
  };

  std::fprintf(out, "stretch tree of depth %d\t check: %lld\n", max_depth + 1, one(max_depth + 1));
  Arena long_pool(arena ? (size_t{1} << (max_depth + 1)) : 0);
  std::unique_ptr<Node> long_lived = arena ? nullptr : make(max_depth);
  ArenaNode* long_lived_arena = arena ? make(max_depth, long_pool) : nullptr;

  for (int d = kMinDepth; d <= max_depth; d += 2) {
    const long long iterations = 1LL << (max_depth - d + kMinDepth);
    long long sum = 0;
    for (long long i = 0; i < iterations; i++) {
      sum += one(d);
      if (progress.on() && (++trees & 1023) == 0) progress.mark(trees);
    }
    std::fprintf(out, "%lld\t trees of depth %d\t check: %lld\n", iterations, d, sum);
  }
  std::fprintf(out, "long lived tree of depth %d\t check: %lld\n", max_depth,
               arena ? check(long_lived_arena) : check(*long_lived));
  progress.mark(trees);
  return std::fclose(out) == 0 ? 0 : 1;
}
