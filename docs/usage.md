# Importing

Imports are either: 
* Binaries (.exe), decompiled with Kuna
* .json exports from Kuna, Ghidra


## Commandline

Run the CLI from the `backend` directory with `uv run graphrev`:

```sh
uv run graphrev decompile /path/to/program.exe
uv run graphrev import-export /path/to/export.json
```


## REST

The analysis REST API also accepts streamed uploads at `POST
/api/v1/binaries/decompile` (raw binary) and `POST /api/v1/binaries/import`
(JSON export), on the analysis backend's default port **8000**. 


## From the viewer UI

Start the UI stack with `just ui`, open <http://127.0.0.1:5173>, and choose
**Import or analyze binary**:

- **Raw binary** (default): select the executable and choose **Analyze binary**.
	The UI uploads it to the viewer backend, which streams it to the analysis
	backend. The analysis backend runs Kuna, then imports the generated export.
- **.json Export**: switch tabs, select an export produced by
	`GraphRevExport.java`, and choose **Import**. This imports the existing
	analysis data without running a decompiler.

The UI shows job progress and selects the imported binary when complete. Raw
binary analysis requires Kuna to be installed and configured on the **analysis
backend host**; a browser upload does not run the decompiler on the user's
computer. Set `GRAPHREV_DECOMPILER_EXECUTABLE` to the Kuna executable path in
the analysis backend environment. If that is unset or unavailable, JSON
imports still work, but raw-binary analysis does not. Upload limits, timeout,
and staging directory are configurable with `GRAPHREV_DECOMPILER_MAX_UPLOAD_BYTES`,
`GRAPHREV_IMPORT_MAX_UPLOAD_BYTES`, `GRAPHREV_DECOMPILER_TIMEOUT_SECONDS`, and
`GRAPHREV_IMPORT_STAGING_DIR`.
