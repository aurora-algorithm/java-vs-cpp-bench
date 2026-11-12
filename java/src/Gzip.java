import java.io.FilterInputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.zip.GZIPOutputStream;

/** Test 1: gzip one file with java.util.zip, which calls the zlib bundled in the JDK. usage: Gzip IN OUT */
public final class Gzip {
    private static final int BUFFER = 64 * 1024;
    private static final long PROGRESS_EVERY = 8L << 20;

    public static void main(String[] args) throws IOException {
        if (args.length != 2) {
            System.err.println("usage: Gzip IN OUT");
            System.exit(2);
        }
        try (Progress progress = new Progress();
             InputStream raw = Files.newInputStream(Path.of(args[0]));
             InputStream in = progress.on() ? new Counting(raw, progress) : raw;
             OutputStream out = new GZIPOutputStream(Files.newOutputStream(Path.of(args[1])), BUFFER)) {
            long n = in.transferTo(out);
            progress.mark(n);
        }
    }

    /** Only in the progress run: logs how much input zlib has been given. */
    private static final class Counting extends FilterInputStream {
        private final Progress progress;
        private long done;
        private long next = PROGRESS_EVERY;

        Counting(InputStream in, Progress progress) {
            super(in);
            this.progress = progress;
        }

        @Override
        public int read(byte[] b, int off, int len) throws IOException {
            int n = super.read(b, off, len);
            if (n > 0) {
                done += n;
                if (done >= next) {
                    progress.mark(done);
                    next += PROGRESS_EVERY;
                }
            }
            return n;
        }
    }
}
