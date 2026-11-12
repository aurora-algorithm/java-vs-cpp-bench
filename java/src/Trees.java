import java.io.IOException;
import java.io.PrintWriter;
import java.nio.file.Files;
import java.nio.file.Path;

/** Test 3: build and walk millions of small binary trees (the Benchmarks Game "binary-trees" job, one thread). usage: Trees DEPTH OUT */
public final class Trees {
    private static final int MIN_DEPTH = 4;

    private static final class Node {
        final Node left;
        final Node right;

        Node(Node left, Node right) {
            this.left = left;
            this.right = right;
        }
    }

    private static Node make(int d) {
        return d > 0 ? new Node(make(d - 1), make(d - 1)) : new Node(null, null);
    }

    private static long check(Node n) {
        return n.left == null ? 1 : 1 + check(n.left) + check(n.right);
    }

    public static void main(String[] args) throws IOException {
        if (args.length != 2) {
            System.err.println("usage: Trees DEPTH OUT");
            System.exit(2);
        }
        int maxDepth = Math.max(MIN_DEPTH + 2, Integer.parseInt(args[0]));
        try (Progress progress = new Progress(); PrintWriter out = new PrintWriter(Files.newBufferedWriter(Path.of(args[1])))) {
            long trees = 0;
            out.printf("stretch tree of depth %d\t check: %d\n", maxDepth + 1, check(make(maxDepth + 1)));
            Node longLived = make(maxDepth);
            for (int d = MIN_DEPTH; d <= maxDepth; d += 2) {
                long iterations = 1L << (maxDepth - d + MIN_DEPTH);
                long sum = 0;
                for (long i = 0; i < iterations; i++) {
                    sum += check(make(d));
                    if (progress.on() && (++trees & 1023) == 0) {
                        progress.mark(trees);
                    }
                }
                out.printf("%d\t trees of depth %d\t check: %d\n", iterations, d, sum);
            }
            out.printf("long lived tree of depth %d\t check: %d\n", maxDepth, check(longLived));
            progress.mark(trees);
        }
    }
}
