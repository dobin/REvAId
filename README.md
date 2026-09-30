# REvAId

**I cant code but i must reverse**

> Cant read asm? dont understand C pointers? Dont know what a basic block is? Tired of having FUN_*? Have no PDBs? Or just being sick of it? Fear not, REvAId is here!

REvAId is a Reverse Engineering Aid for/with aI. 

It stores functions (not basic blocks), including the following data:
* Assembly source
* Decompiled C source (kuna, ghidra)
* Callees and callers of each function
* Data references (.data, .rdata)
* LLM function summaries

The idea is to provide a function based view to a binary, similarly to 
source code. But heavily use AND enable AI.

Integrated projects:
* REvAId-UI: A graphical ui used to interactively explore unknown codebases
* REvAId-mcp: A MCP server to enable AI agents to efficiently reverse engineer the functionality of binaries

You can think of it mostly as ghidra-mcp (but not depending on ghidra, and not only supporting a single file). The full stack is completely free
and open source (unlike IDA or BinaryNinja for example), and not from the NSA. 

The MCP server is mostly used to mass reverse-engineer many binaries, 
e.g. for BYOVD. 

AI data augmentation: Per-function AI purpose and summary of what
the function is doing, via: 
* REvAId-ui: on-view function LLM summaries
* REvAId-mcp enables AI agents to also add its conclusions to the DB

This is 100% vibe coded. 


## Prerequisites

Make sure these are available:

- [`uv`](https://docs.astral.sh/uv/) (Python 3.12 package/env manager)
- [`just`](https://github.com/casey/just) (task runner)
- Node.js 22+ and npm (for the UI only)
- [`kuna`](https://github.com/noelo-lab/kuna)


## Usage

Setup:
```
$ just setup
$ just migrate
```

Analyze a binary:
```
$ export GRAPHREV_DECOMPILER_EXECUTABLE=/opt/kuna/kuna
$ uv run graphrev decompile data/redtest.exe
```

This stores the binary information in the sqlite database of 
REvAId. 

Use one of the following interface options to interact with the data: 
* MCP: For AI agents (claude, opencode...)
* UI: HTML interface
* WEB: REST interface
* SQL: Use the `backend/graphrev.db` by yourself


### Interface: MCP

MCP server for agent:
```
$ just mcp
```

The default MCP endpoint is:

```text
http://127.0.0.1:8001/mcp
```


### Interace: REvAId-UI

Configure the LLM provider (optional, but recommended) in `backend/.env`, copy from `backend/.env.example`:

```sh
# opencode go
GRAPHREV_LLM_MODEL=openai/deepseek-v4-flash
GRAPHREV_LLM_API_BASE=https://opencode.ai/zen/go/v1
GRAPHREV_LLM_API_KEY=sk-
```

start the REvAId-ui:
```
$ just ui
```

And open `http://localhost:5173`

For detailed information, see [revaid-ui](https://github.com/dobin/REvAId/blob/main/docs/revaid-ui.md)



## Other ingestion

Default usecase is just to use kuna with `graphrev decompile`, already integrated. 


### Ingestion: Kuna

If you want to use kuna manually (mostly for testing and development). Or to perform the decompilation somewhere else, as
it can take some time for big files. 

Decompile a binary and save to json:
```
$ ./kuna decompile-graph test.exe -o kuna.json
```

Import json: 
```
$ uv run graphrev import-export kuna.json --binary test.exe
```

`--binary` is optional, but recommended. It records the source PE's path and
SHA-256 and parses the PE to extract data items and references during ingestion.


### Ingestion: Ghidra

If you want to use ghidra.

With ghidra we need to:

1) Open binary in Ghidra and let it analyze it
2) Export Ghidra data with the included script to JSON
3) Import JSON into REvAId

To analyze a binary, we first needs its data: function assembly, disassembly (c code), and callers/callees (xrefs). 

This is currently achieved with a ghidra script. 

0) Open your binary in ghidra, let it analyze it
1) Click "Window" -> "Script Manager"
2) Add a new file Java with filename `GraphRevExport.java`
3) Paste [GraphRevExport.java](https://github.com/dobin/REvAId/blob/main/tools/ghidra/GraphRevExport.java)
4) Run the script
5) If asked to skip disassembly, say NO (except if you want to use AI Agent, not AI LLM)
6) Grab a cuppa and wait till the export is finished

Import json: 
```
$ uv run graphrev import-export ghidra.json --binary test.exe
```

As with Kuna exports, `--binary` enables source-PE metadata and data-reference
extraction.