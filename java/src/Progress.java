import java.io.FileWriter;
import java.io.IOException;
import java.io.PrintWriter;
import java.io.UncheckedIOException;
import java.time.Duration;
import java.time.Instant;

/** Appends "units<TAB>seconds" lines to $PROGRESS_OUT when set; seconds count from the moment the OS created the JVM process. */
final class Progress implements AutoCloseable {
    private static final Instant START = ProcessHandle.current().info().startInstant().orElseThrow();
    private final PrintWriter out;

    Progress() {
        String path = System.getenv("PROGRESS_OUT");
        try {
            out = path == null ? null : new PrintWriter(new FileWriter(path));
        } catch (IOException e) {
            throw new UncheckedIOException(e);
        }
    }

    boolean on() {
        return out != null;
    }

    void mark(long units) {
        if (out != null) {
            double s = Duration.between(START, Instant.now()).toNanos() / 1e9;
            out.printf("%d\t%.6f%n", units, s);
        }
    }

    @Override
    public void close() {
        if (out != null) {
            out.close();
        }
    }
}
