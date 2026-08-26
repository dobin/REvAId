/* GraphRevExport.java
 *
 * Ghidra script that exports every function of the current program to a single
 * JSON file shaped for GraphRev ingestion.
 *
 * The output JSON maps 1:1 onto the backend ingestion DTOs in
 *   backend/src/graphrev/adapters/ghidra/base.py
 * namely RawBinary, RawFunction (RawParam), and RawEdge / FunctionKind. Keeping
 * the field names aligned means a future file/REST GhidraAdapter (Increment I12)
 * can load this file with no contract change.
 *
 * Deliberately zero-dependency: Java has no stdlib JSON and Gson is not
 * guaranteed to be on Ghidra's classpath across versions, so JSON is emitted by
 * a tiny hand-rolled writer (see JsonWriter below). This keeps the script
 * portable across Ghidra releases.
 *
 * Robustness follows the pipeline's A4 rule ("report failures, never abort"):
 * a decompilation error/timeout yields codeC = null and a logged warning, and
 * ingestion continues.
 *
 * @category GraphRev
 * @runtime Ghidra (Java) — run from the Script Manager (GUI) or headless
 *          analyzeHeadless via -postScript.
 */

import java.io.File;
import java.io.IOException;
import java.io.PrintWriter;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.util.ArrayList;
import java.util.Iterator;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Set;

import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileOptions;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.decompiler.DecompiledFunction;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.FunctionIterator;
import ghidra.program.model.listing.Instruction;
import ghidra.program.model.listing.InstructionIterator;
import ghidra.program.model.listing.Listing;
import ghidra.program.model.listing.Parameter;
import ghidra.program.model.listing.Program;
import ghidra.program.model.symbol.ExternalLocation;
import ghidra.program.model.symbol.ExternalManager;
import ghidra.program.model.symbol.Reference;
import ghidra.program.model.symbol.RefType;

public class GraphRevExport extends GhidraScript {

    /** Bump when the emitted schema changes shape. */
    private static final int SCHEMA_VERSION = 1;

    /** Per-function decompiler timeout, in seconds. */
    private static final int DECOMPILE_TIMEOUT_SECONDS = 60;

    private DecompInterface decompiler;

    @Override
    protected void run() throws Exception {
        long startedAt = System.nanoTime();
        Program program = currentProgram;
        if (program == null) {
            printerr("GraphRevExport: no program is open.");
            return;
        }

        File outFile = ensureJsonExtension(resolveOutputFile(program));
        String version = resolveVersion();
        boolean skipDecompilation = shouldSkipDecompilation();

        println("GraphRevExport: exporting " + program.getName() + " -> " + outFile.getAbsolutePath());
        println(
                "GraphRevExport: mode = "
                        + (skipDecompilation ? "fast (no decompiled C)" : "complete"));

        if (!skipDecompilation) {
            decompiler = new DecompInterface();
            DecompileOptions options = new DecompileOptions();
            decompiler.setOptions(options);
            decompiler.openProgram(program);
        }

        try {
            long collectionStartedAt = System.nanoTime();
            List<Function> functions = collectFunctions(program);
            long collectionNanos = System.nanoTime() - collectionStartedAt;
            monitor.initialize(functions.size());
            monitor.setMessage("Exporting functions");

            StringBuilder functionsJson = new StringBuilder();
            StringBuilder edgesJson = new StringBuilder();
            Set<String> emittedEdges = new LinkedHashSet<>(); // dedupe (caller,callee) pairs
            int functionCount = 0;
            int edgeCount = 0;

            long exportStartedAt = System.nanoTime();
            for (Function fn : functions) {
                monitor.checkCancelled();
                monitor.setMessage("Exporting " + fn.getName());

                appendFunctionJson(functionsJson, functionCount, fn, skipDecompilation);
                functionCount++;

                edgeCount += appendEdgesForFunction(edgesJson, emittedEdges, edgeCount, fn);

                monitor.incrementProgress(1);
            }
            long exportNanos = System.nanoTime() - exportStartedAt;

            long writeStartedAt = System.nanoTime();
            writeJson(outFile, program, version, functionsJson, edgesJson, functionCount, edgeCount);
            long writeNanos = System.nanoTime() - writeStartedAt;
            println("GraphRevExport: wrote " + functionCount + " functions, " + edgeCount + " edges.");
            println(
                    "GraphRevExport: timings — collect "
                            + formatMillis(collectionNanos)
                            + ", export "
                            + formatMillis(exportNanos)
                            + ", write "
                            + formatMillis(writeNanos)
                            + ", total "
                            + formatMillis(System.nanoTime() - startedAt));
        } finally {
            if (decompiler != null) {
                decompiler.dispose();
            }
        }
    }

    // ------------------------------------------------------------------ setup

    /**
     * Output path: first script arg in headless mode, else a GUI file prompt,
     * defaulting to {@code <program>_graphrev.json} in the user's home dir.
     */
    private File resolveOutputFile(Program program) throws Exception {
        String[] args = getScriptArgs();
        if (args.length >= 1 && args[0] != null && !args[0].isEmpty()) {
            return new File(args[0]);
        }
        String defaultName = program.getName() + "_graphrev.json";
        File defaultFile = new File(System.getProperty("user.home"), defaultName);
        try {
            return askFile("GraphRev export destination", "Save").getCanonicalFile();
        } catch (Exception headless) {
            // askFile throws in headless mode with no arg — fall back to default.
            return defaultFile;
        }
    }

    /** Ensure GUI-selected and headless output paths use the JSON extension. */
    private File ensureJsonExtension(File file) {
        String path = file.getPath();
        if (path.toLowerCase().endsWith(".json")) {
            return file;
        }
        return new File(path + ".json");
    }

    /**
     * Ask GUI users whether to omit decompiled C for a faster export. In
     * headless mode the prompt is unavailable, so preserve the complete export
     * as the backward-compatible default.
     */
    private boolean shouldSkipDecompilation() {
        try {
            return askYesNo(
                    "GraphRev export mode",
                    "Skip decompilation?\n\n"
                            + "Yes: fast export with assembly and call graph, but codeC is null.\n"
                            + "No: complete export with decompiled C.");
        } catch (Exception headless) {
            return false;
        }
    }

    private String formatMillis(long nanos) {
        return String.format("%.1f ms", nanos / 1_000_000.0);
    }

    /** Version is free text (AS11); optional second script arg overrides "". */
    private String resolveVersion() {
        String[] args = getScriptArgs();
        if (args.length >= 2 && args[1] != null) {
            return args[1];
        }
        return "";
    }

    /**
     * All in-program functions followed by function-valued external locations.
     *
     * {@code Listing.getFunctions(true)} does not enumerate the EXTERNAL
     * address space. Consequently, a PE import such as
     * {@code ADVAPI32.DLL::EventRegister} could be Ghidra-resolved and appear
     * as a call target, yet have no function object in the export. Walk the
     * ExternalManager explicitly so those targets become GraphRev functions
     * and their call edges can resolve to real rows rather than placeholders.
     */
    private List<Function> collectFunctions(Program program) {
        Listing listing = program.getListing();
        FunctionIterator it = listing.getFunctions(true);
        List<Function> out = new ArrayList<>();
        Set<Address> seenEntryPoints = new LinkedHashSet<>();
        while (it.hasNext()) {
            Function function = it.next();
            if (seenEntryPoints.add(function.getEntryPoint())) {
                out.add(function);
            }
        }

        ExternalManager externalManager = program.getExternalManager();
        for (String libraryName : externalManager.getExternalLibraryNames()) {
            Iterator<ExternalLocation> locations = externalManager.getExternalLocations(libraryName);
            while (locations.hasNext()) {
                ExternalLocation location = locations.next();
                Function function = location.getFunction();
                if (function != null && seenEntryPoints.add(function.getEntryPoint())) {
                    out.add(function);
                }
            }
        }
        return out;
    }

    // -------------------------------------------------------------- functions

    /** Emit one RawFunction-shaped object into {@code sb}. */
    private void appendFunctionJson(
            StringBuilder sb, int index, Function fn, boolean skipDecompilation) {
        if (index > 0) {
            sb.append(",\n");
        }

        long address = fn.getEntryPoint().getOffset();
        String kind = classifyKind(fn);
        boolean hasBody = hasExportableBody(fn);
        FunctionBodyData bodyData = hasBody ? inspectBody(fn) : FunctionBodyData.EMPTY;
        String codeC = hasBody && !skipDecompilation ? decompile(fn) : null;

        JsonWriter w = new JsonWriter(sb);
        w.beginObject();
        w.field("address", address);
        w.field("name", exportName(fn));
        appendParameters(w, fn);
        w.fieldOrNull("signature", fn.getPrototypeString(false, false));
        w.fieldOrNull("assembly", bodyData.assembly);
        w.fieldOrNull("codeC", codeC);
        w.field("kind", kind);
        w.field("hasIndirectCalls", bodyData.hasIndirectCalls);
        w.field("isEntryPoint", isEntryPoint(fn));
        w.endObject();
    }

    /** True only for functions whose body can provide assembly and decompiled C. */
    private boolean hasExportableBody(Function fn) {
        return !fn.isExternal()
                && !fn.isThunk()
                && fn.getBody() != null
                && !fn.getBody().isEmpty();
    }

    /**
     * Give external symbols the same library-qualified name Ghidra displays,
     * for example {@code ADVAPI32.DLL::EventRegister}. A plain
     * {@link Function#getName()} drops that namespace and makes identically
     * named imports from different DLLs indistinguishable in GraphRev.
     */
    private String exportName(Function fn) {
        if (!fn.isExternal()) {
            return fn.getName();
        }
        ExternalLocation location = fn.getExternalLocation();
        if (location == null) {
            return fn.getName();
        }
        String libraryName = location.getLibraryName();
        String label = location.getLabel();
        if (libraryName == null || libraryName.isEmpty()) {
            return label == null || label.isEmpty() ? fn.getName() : label;
        }
        return libraryName + "::" + (label == null || label.isEmpty() ? fn.getName() : label);
    }

    private void appendParameters(JsonWriter w, Function fn) {
        w.rawKey("parameters");
        StringBuilder arr = w.target();
        arr.append('[');
        Parameter[] params = fn.getParameters();
        for (int i = 0; i < params.length; i++) {
            if (i > 0) {
                arr.append(',');
            }
            Parameter p = params[i];
            JsonWriter pw = new JsonWriter(arr);
            pw.beginObject();
            pw.field("ordinal", p.getOrdinal());
            pw.field("name", p.getName() == null ? ("param_" + i) : p.getName());
            pw.field("type", p.getDataType() == null ? "undefined" : p.getDataType().getDisplayName());
            pw.endObject();
        }
        arr.append(']');
        w.markFieldWritten();
    }

    /**
     * Map a Ghidra Function onto GraphRev's FunctionKind. Never returns
     * "placeholder" — those are materialised by ingestion from unresolved
     * cross-module edges (B17), not reported by an adapter.
     */
    private String classifyKind(Function fn) {
        if (fn.isThunk()) {
            return "thunk";
        }
        if (fn.isExternal()) {
            return "external";
        }
        // An imported function typically lives in the EXTERNAL memory block or
        // resolves through the import table; treat body-less library entries as
        // "import" so library calls appear with a distinct kind (A8).
        if (fn.getBody() == null || fn.getBody().isEmpty()) {
            return "import";
        }
        return "normal";
    }

    private boolean isEntryPoint(Function fn) {
        String name = fn.getName();
        if (name == null) {
            return false;
        }
        // Common entry symbols across PE/ELF; a real bridge may refine this.
        return name.equals("main")
                || name.equals("WinMain")
                || name.equals("wWinMain")
                || name.equals("DllMain")
                || name.equals("entry")
                || name.equals("_start");
    }

    // --------------------------------------------------------------- assembly

    /**
     * Traverse a function body once to build its assembly and detect computed
     * or indirect calls. The JSON assembly format is intentionally unchanged.
     */
    private FunctionBodyData inspectBody(Function fn) {
        Listing listing = fn.getProgram().getListing();
        InstructionIterator it = listing.getInstructions(fn.getBody(), true);
        StringBuilder sb = new StringBuilder();
        boolean first = true;
        boolean hasIndirectCalls = false;
        while (it.hasNext()) {
            Instruction ins = it.next();
            if (!first) {
                sb.append('\n');
            }
            first = false;
            sb.append(ins.getAddress().toString()).append("  ").append(ins.toString());
            if (!hasIndirectCalls) {
                for (Reference ref : ins.getReferencesFrom()) {
                    RefType rt = ref.getReferenceType();
                    if (rt.isCall() && (rt.isComputed() || rt.isIndirect())) {
                        hasIndirectCalls = true;
                        break;
                    }
                }
            }
        }
        return new FunctionBodyData(sb.length() == 0 ? null : sb.toString(), hasIndirectCalls);
    }

    // ---------------------------------------------------------- decompilation

    /** Decompiled C, or null on error/timeout (logged, never fatal — A4). */
    private String decompile(Function fn) {
        try {
            DecompileResults results =
                    decompiler.decompileFunction(fn, DECOMPILE_TIMEOUT_SECONDS, monitor);
            String err = results.getErrorMessage();
            if (err != null && !err.isEmpty()) {
                printerr("GraphRevExport: decompile warning for " + fn.getName() + ": " + err);
            }
            DecompiledFunction decompiled = results.getDecompiledFunction();
            return decompiled == null ? null : decompiled.getC();
        } catch (Exception e) {
            printerr("GraphRevExport: decompile failed for " + fn.getName() + ": " + e.getMessage());
            return null;
        }
    }

    // ------------------------------------------------------------------ edges

    /**
     * Emit one RawEdge per unique (caller,callee) pair reachable from {@code fn}.
     * Self-edges (recursion) are kept. Returns the number of new edges written.
     */
    private int appendEdgesForFunction(
            StringBuilder sb, Set<String> emitted, int alreadyWritten, Function caller) {
        int written = 0;
        for (Function called : caller.getCalledFunctions(monitor)) {
            // PE/ELF imports are frequently represented as a local thunk. The
            // resolved external function is the useful graph target; exporting
            // the thunk address would leave ADVAPI32.DLL::EventRegister (etc.)
            // disconnected despite Ghidra having resolved it.
            Function callee = resolveEdgeCallee(called);
            long callerAddr = caller.getEntryPoint().getOffset();
            long calleeAddr = callee.getEntryPoint().getOffset();
            String dedupeKey = callerAddr + "->" + calleeAddr;
            if (!emitted.add(dedupeKey)) {
                continue;
            }
            String calleeModule = resolveCalleeModule(callee);

            if (alreadyWritten + written > 0) {
                sb.append(",\n");
            }
            JsonWriter w = new JsonWriter(sb);
            w.beginObject();
            w.field("callerAddress", callerAddr);
            w.field("calleeAddress", calleeAddr);
            w.fieldOrNull("calleeModule", calleeModule);
            w.endObject();
            written++;
        }
        return written;
    }

    /** Return the final external target of an import thunk, otherwise {@code callee}. */
    private Function resolveEdgeCallee(Function callee) {
        if (!callee.isThunk()) {
            return callee;
        }
        Function thunked = callee.getThunkedFunction(true);
        return thunked != null && thunked.isExternal() ? thunked : callee;
    }

    /**
     * The library/namespace name when the callee lives outside this program
     * body — the signal ingestion uses to create a placeholder row (B17).
     * Returns null for ordinary in-program callees.
     */
    private String resolveCalleeModule(Function callee) {
        if (callee.isExternal()) {
            String libName = callee.getExternalLocation() != null
                    ? callee.getExternalLocation().getLibraryName()
                    : null;
            return libName != null ? libName : "EXTERNAL";
        }
        if (callee.isThunk()) {
            Function thunked = callee.getThunkedFunction(true);
            if (thunked != null && thunked.isExternal()) {
                String libName = thunked.getExternalLocation() != null
                        ? thunked.getExternalLocation().getLibraryName()
                        : null;
                return libName != null ? libName : "EXTERNAL";
            }
        }
        return null;
    }

    private static final class FunctionBodyData {
        static final FunctionBodyData EMPTY = new FunctionBodyData(null, false);

        final String assembly;
        final boolean hasIndirectCalls;

        FunctionBodyData(String assembly, boolean hasIndirectCalls) {
            this.assembly = assembly;
            this.hasIndirectCalls = hasIndirectCalls;
        }
    }

    // ----------------------------------------------------------------- output

    private void writeJson(
            File outFile,
            Program program,
            String version,
            StringBuilder functionsJson,
            StringBuilder edgesJson,
            int functionCount,
            int edgeCount)
            throws IOException {

        StringBuilder doc = new StringBuilder(functionsJson.length() + edgesJson.length() + 512);
        JsonWriter w = new JsonWriter(doc);
        w.beginObject();
        w.field("schemaVersion", SCHEMA_VERSION);

        w.rawKey("binary");
        JsonWriter b = new JsonWriter(doc);
        b.beginObject();
        b.field("name", program.getName());
        b.field("version", version);
        b.fieldOrNull("sourcePath", program.getExecutablePath());
        b.fieldOrNull("sha256", program.getExecutableSHA256());
        b.field("functionCount", functionCount);
        b.field("edgeCount", edgeCount);
        b.endObject();
        w.markFieldWritten();

        w.rawKey("functions");
        doc.append("[\n").append(functionsJson).append("\n]");
        w.markFieldWritten();

        w.rawKey("edges");
        doc.append("[\n").append(edgesJson).append("\n]");
        w.markFieldWritten();

        w.endObject();

        File parent = outFile.getParentFile();
        if (parent != null) {
            Files.createDirectories(parent.toPath());
        }
        try (PrintWriter out =
                new PrintWriter(Files.newBufferedWriter(outFile.toPath(), StandardCharsets.UTF_8))) {
            out.write(doc.toString());
        }
    }

    // ------------------------------------------------------- tiny JSON writer

    /**
     * Minimal JSON object writer over a shared StringBuilder. Handles comma
     * placement between fields and RFC 8259 string escaping. Deliberately not a
     * general-purpose serializer — just enough for this fixed schema.
     */
    private static final class JsonWriter {
        private final StringBuilder sb;
        private boolean hasField;

        JsonWriter(StringBuilder sb) {
            this.sb = sb;
        }

        StringBuilder target() {
            return sb;
        }

        void beginObject() {
            sb.append('{');
            hasField = false;
        }

        void endObject() {
            sb.append('}');
        }

        /** Write only the key and separator; the caller appends the raw value. */
        void rawKey(String key) {
            comma();
            escape(key);
            sb.append(':');
        }

        /** Signal that a value written via {@link #rawKey}/{@link #target} is complete. */
        void markFieldWritten() {
            hasField = true;
        }

        void field(String key, String value) {
            comma();
            escape(key);
            sb.append(':');
            escape(value);
            hasField = true;
        }

        void field(String key, long value) {
            comma();
            escape(key);
            sb.append(':').append(value);
            hasField = true;
        }

        void field(String key, boolean value) {
            comma();
            escape(key);
            sb.append(':').append(value);
            hasField = true;
        }

        void fieldOrNull(String key, String value) {
            comma();
            escape(key);
            sb.append(':');
            if (value == null) {
                sb.append("null");
            } else {
                escape(value);
            }
            hasField = true;
        }

        private void comma() {
            if (hasField) {
                sb.append(',');
            }
        }

        private void escape(String s) {
            sb.append('"');
            for (int i = 0; i < s.length(); i++) {
                char c = s.charAt(i);
                switch (c) {
                    case '"':
                        sb.append("\\\"");
                        break;
                    case '\\':
                        sb.append("\\\\");
                        break;
                    case '\n':
                        sb.append("\\n");
                        break;
                    case '\r':
                        sb.append("\\r");
                        break;
                    case '\t':
                        sb.append("\\t");
                        break;
                    case '\b':
                        sb.append("\\b");
                        break;
                    case '\f':
                        sb.append("\\f");
                        break;
                    default:
                        if (c < 0x20) {
                            sb.append(String.format("\\u%04x", (int) c));
                        } else {
                            sb.append(c);
                        }
                }
            }
            sb.append('"');
        }
    }
}
