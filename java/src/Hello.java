import java.lang.management.ManagementFactory;

/** Startup: the smallest program, so hyperfine measures only what it takes to start and exit. "info" prints the JVM's view of the machine. */
public final class Hello {
    public static void main(String[] args) {
        if (args.length == 1 && args[0].equals("info")) {
            System.out.println("cpus " + Runtime.getRuntime().availableProcessors());
            System.out.println("max_heap " + Runtime.getRuntime().maxMemory());
            ManagementFactory.getGarbageCollectorMXBeans().forEach(gc -> System.out.println("gc " + gc.getName()));
            return;
        }
        System.out.println("hello");
    }
}
