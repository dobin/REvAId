# REvAId

**I cant code but i must reverse**

> Cant read asm? dont understand C pointers? Dont know what a basic block is? Tired of having FUN_*? Or just being sick of it? Fear not, REvAId is here!

REvAId is a semantic function graph explorer for binary reverse
engineering: it renders a binary's call graph as interactive cards, lazily
summarizes functions with an LLM, and lets an analyst annotate what they
find. 

Purpose: 
* Reverse engineer binaries without reading C/ASM code, only LLM summaries in a function call graph (ai-assited reversing)
* Manually verify the results of your super duper next generation AI reversing analysis (ai-reversing verification)

This is 100% vibe coded. See `IDEA.md`, `PRD.md`, `TAD.md`.

## Screenshots

Reversing MS Defender: 

![Function graph explorer](docs/img/REvAId-1.png)


AI Summaries for each function:

![Function summary view](docs/img/REvAId-2.png)


## Usage

1) Let Ghidra analyze your binary
2) Export Ghidra data with the included script to JSON
3) Import JSON into REvAId
4) Explore the code base

There are two AI providers available: 
* LLM based: Simple. Queries the LLM with the disassembled function code
* Agent based: Complex. Queries OpenCode agent (using Ghidra-MCP) for function analysis


## Prerequisites

- [`uv`](https://docs.astral.sh/uv/) (Python 3.12 package/env manager)
- Node.js 22+ and npm
- [`just`](https://github.com/casey/just) (task runner)


## Quickstart

```sh
just setup    # uv sync (backend) + npm install (frontend)
just migrate  # alembic upgrade head — the ONLY way the DB schema is created
just dev      # runs the API (uvicorn, :8000) and the SPA (Vite, :5173) together
```

Then open http://127.0.0.1:5173 — you should see a small panel showing live
`/health` and `/config` data, proving the frontend, backend, and database are
wired together end to end.


## Ghidra Export

To analyze a binary, we first needs its data: function assembly, disassembly (c code), and callers/callees (xrefs). 

This is currently achieved with a ghidra script. 

0) Open your binary in ghidra, let it analyze it
1) Click "Window" -> "Script Manager"
2) Add a new file Java with filename `GraphRevExport.java`
3) Paste [GraphRevExport.java](https://github.com/dobin/REvAId/blob/main/tools/ghidra/GraphRevExport.java)
4) Run the script
5) If asked to skip disassembly, say NO (except if you want to use AI Agent, not AI LLM)
6) Grab a cuppa and wait till the export is finished

Then in REvAId, click "import binary", and select that JSON file. 


## Everyday commands

| Command | What it does |
| --- | --- |
| `just dev` | Run API + web concurrently (F3) |
| `just api` / `just web` | Run just one side |
| `just migrate` | Apply pending Alembic migrations |
| `just revision name="add x"` | Autogenerate a new migration from `db/models.py` |
| `just db-reset` | Delete the local SQLite file and re-migrate from scratch |
| `just test` | Run backend (pytest) and frontend (vitest) test suites |
| `just lint` | ruff, mypy --strict, import-linter, eslint, tsc, magic-number guard |
| `just fmt` | Auto-format both backend and frontend |
| `just gen-types` | Regenerate `frontend/src/api/generated.ts` from the live OpenAPI schema |


## Config


### LLM summaries

Set `GRAPHREV_LLM_ADAPTER=litellm` to enable the LLM analysis. 


| Variable | Meaning |
| --- | --- |
| `GRAPHREV_LLM_ADAPTER=litellm` | Select the litellm adapter |
| `GRAPHREV_LLM_MODEL` | litellm router string, e.g. `anthropic/claude-sonnet-4-5`, `openai/gpt-4o`, `ollama/llama3` |
| `GRAPHREV_LLM_API_KEY` | Provider API key (put it in `backend/.env`, not the shell) |
| `GRAPHREV_LLM_API_BASE` | Base URL for self-hosted/proxied endpoints (Ollama, vLLM, an LLM gateway); leave unset for hosted providers |

Examples:

```sh
# Anthropic (key from https://console.anthropic.com/)
GRAPHREV_LLM_ADAPTER=litellm
GRAPHREV_LLM_MODEL=anthropic/claude-sonnet-4-5
GRAPHREV_LLM_API_KEY=sk-ant-...

# Local Ollama — no key needed
GRAPHREV_LLM_ADAPTER=litellm
GRAPHREV_LLM_MODEL=ollama/llama3
GRAPHREV_LLM_API_BASE=http://127.0.0.1:11434
```


### Public Mode

Set `GRAPHREV_PUBLIC_MODE=true` when exposing an instance to anonymous
visitors