
# REvAId-UI


REvAId-UI is a semantic function graph explorer for binary reverse
engineering: it renders a binary's call graph as interactive cards, lazily
summarizes functions with an LLM, and lets an analyst annotate what they
find.

Purpose: 
* Reverse engineer binaries without reading C/ASM code, only LLM summaries in a function call graph (ai-assited reversing)
* Manually verify the results of your super duper next generation AI reversing analysis (ai-reversing verification)
* Dont be dependent on PDB

Live at [REvAId.r00ted.ch](https://revaid.r00ted.ch)



## Screenshots

All function names are AI generated. The quick summary & function name is generated based on decompiled C. 

Callees and callers can be fan-out to explore the binary (without reading any code). 

### Reversing MS Defender process injection detection

![Function graph explorer](docs/img/REvAId-1.png)


### Detailed AI Summary

![Function summary view](docs/img/REvAId-2.png)


## Quickstart


```sh
just setup    # uv sync (backend) + npm install (frontend)
just migrate  # migrate both the analysis and viewer databases
just dev      # analysis (:8000), viewer (:8002), and SPA (:5173)
just prod     # production-mode analysis, viewer, and SPA services
```

Open http://127.0.0.1:5173. The frontend sends browser API requests to the
viewer backend at `http://127.0.0.1:8002`; the viewer talks to the analysis
backend at `http://127.0.0.1:8000` through its internal API.


## LLM summaries

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


## Public Mode

Set `GRAPHREV_PUBLIC_MODE=true` when exposing an instance to anonymous
visitors

## Caddy

The recommended deployment uses one public origin and lets Caddy route API
requests to the viewer backend, which calls the analysis backend on loopback. `just prod` binds services to
loopback by default:

```caddyfile
graphrev.example.com {
	reverse_proxy /api/* 127.0.0.1:8002
	reverse_proxy 127.0.0.1:4173
}
```

Pass the public hostname so Vite accepts Caddy's forwarded `Host` header:

```sh
just prod domain=graphrev.example.com
```



## Architecture

The two ASGI applications live in separate source packages: the analysis
backend is `backend/src/revaid` (`revaid.main:app`), and the viewer backend is
`backend/src/revaid_ui` (`revaid_ui.main:app`). They share lower-level domain
and persistence contracts only through `backend/src/revaid_contracts`; the
viewer obtains analysis facts through the authenticated internal HTTP API.
Each service has its own models, repositories, services, routes and startup
lifecycle. Start either independently with `just analysis` or `just viewer`.
For production, use `just prod domain=graphrev.example.com`; it builds the SPA
and starts both backends plus the static SPA preview.

The React app talks only to the **viewer backend** in split mode. The viewer backend calls the **analysis
backend** through an authenticated, fixed internal API. Upload bodies are streamed
through the viewer backend with the same configured byte limits and staged/queued only by the analysis backend; job polling
and cancellation are also forwarded to the analysis backend. Raw-binary decompilation therefore requires
the analysis backend's configured local decompiler and staging directory. The viewer backend periodically emits
a `reconcile` SSE invalidation because a cross-process event relay is not implemented yet;
this causes clients to refetch, but does not forward the analysis backend's per-summary/queue events.
Run exactly one Uvicorn worker for each analysis-backend process: import-job, summary-worker, and event
state are process-local. To run the analysis backend without
the optional UI, install the backend, apply only its schema, and start
`uv run uvicorn revaid.main:app`; it does not require npm, a browser, or a
viewer database. Start the viewer backend separately with
`uv run uvicorn revaid_ui.main:app` and configure
`GRAPHREV_ANALYSIS_INTERNAL_URL` plus the shared internal token.



----
There are two AI providers available: 
* LLM based: Simple. Queries the LLM with the disassembled function code
* Agent based: Complex. Queries OpenCode agent (using Ghidra-MCP) for function analysis
