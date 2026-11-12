import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Arrays;
import java.util.List;
import java.util.stream.Stream;

/**
 * Test 2: box-blur every photo in a folder (raw RGB, 8-byte header: width, height as little-endian u32).
 * usage: Blur IN_DIR OUT_DIR RADIUS. Same loops as cpp/blur.cpp, integer maths only, so both write the same bytes.
 */
public final class Blur {
    static void blur(byte[] src, byte[] tmp, byte[] dst, int w, int h, int r) {
        int w3 = w * 3;
        int d = 2 * r + 1;
        int m = (65536 + d / 2) / d;
        int[] acc = new int[w3];
        for (int y = 0; y < h; y++) {
            Arrays.fill(acc, 0);
            for (int k = -r; k <= r; k++) {
                int base = Math.clamp(y + k, 0, h - 1) * w3;
                for (int i = 0; i < w3; i++) {
                    acc[i] += src[base + i] & 0xff;
                }
            }
            int o = y * w3;
            for (int i = 0; i < w3; i++) {
                tmp[o + i] = (byte) ((acc[i] * m + 32768) >> 16);
            }
        }
        byte[] pad = new byte[(w + 2 * r) * 3];
        for (int y = 0; y < h; y++) {
            int row = y * w3;
            for (int x = 0; x < r; x++) {
                System.arraycopy(tmp, row, pad, x * 3, 3);
                System.arraycopy(tmp, row + w3 - 3, pad, (r + w + x) * 3, 3);
            }
            System.arraycopy(tmp, row, pad, r * 3, w3);
            Arrays.fill(acc, 0);
            for (int k = 0; k < d; k++) {
                int p = k * 3;
                for (int i = 0; i < w3; i++) {
                    acc[i] += pad[p + i] & 0xff;
                }
            }
            for (int i = 0; i < w3; i++) {
                dst[row + i] = (byte) ((acc[i] * m + 32768) >> 16);
            }
        }
    }

    private static int le32(byte[] b, int at) {
        return (b[at] & 0xff) | (b[at + 1] & 0xff) << 8 | (b[at + 2] & 0xff) << 16 | (b[at + 3] & 0xff) << 24;
    }

    public static void main(String[] args) throws IOException {
        if (args.length != 3) {
            System.err.println("usage: Blur IN_DIR OUT_DIR RADIUS");
            System.exit(2);
        }
        int r = Integer.parseInt(args[2]);
        List<Path> photos;
        try (Stream<Path> s = Files.list(Path.of(args[0]))) {
            photos = s.filter(p -> p.toString().endsWith(".rgb")).sorted().toList();
        }
        if (photos.isEmpty()) {
            throw new IOException("no .rgb files in " + args[0]);
        }
        Path outDir = Files.createDirectories(Path.of(args[1]));
        try (Progress progress = new Progress()) {
            long done = 0;
            for (Path photo : photos) {
                byte[] hdr = new byte[8];
                byte[] src;
                int w;
                int h;
                try (FileInputStream in = new FileInputStream(photo.toFile())) {
                    if (in.readNBytes(hdr, 0, 8) != 8) {
                        throw new IOException("short header: " + photo);
                    }
                    w = le32(hdr, 0);
                    h = le32(hdr, 4);
                    src = new byte[w * h * 3];
                    if (in.readNBytes(src, 0, src.length) != src.length) {
                        throw new IOException("short read: " + photo);
                    }
                }
                byte[] tmp = new byte[src.length];
                byte[] dst = new byte[src.length];
                blur(src, tmp, dst, w, h, r);
                try (FileOutputStream out = new FileOutputStream(outDir.resolve(photo.getFileName()).toFile())) {
                    out.write(hdr);
                    out.write(dst);
                }
                progress.mark(++done);
            }
        }
    }
}
