# Architecture

REvAId consist of two components: 
* A analysis backend for binary reversing (REST & MCP)
* A frontend UI to explore binaries

Start the whole UI stack with `just dev` and open <http://127.0.0.1:5173>.


| Service | Default port / endpoint | Used by |
| --- | --- | --- |
| Frontend (Vite dev) | `5173` | Analysts in a browser |
| Frontend (production preview) | `4173` | Analysts in a browser |
| Viewer backend | `8002` | Frontend; serves UI API |
| Analysis backend | `8000` | Viewer backend and direct API/ingestion clients |
| MCP server | `8001/mcp` | MCP-compatible AI agents |



## Analysis API (& MCP)

The analysis backend (`backend/src/revaid`) owns imported binary/function data,
search, ingestion, and summary work. It listens at
**http://127.0.0.1:8000** by default (`just analysis`). 

The optional **MCP server** is an agent-facing interface to that analysis data.
Start it with `just mcp`; its Streamable HTTP endpoint is
**http://127.0.0.1:8001/mcp** by default. 


## Graph Reversing UI

The UI is for people exploring a binary's function graph, summaries, and analyst annotations.

- **Frontend** (`frontend/`) — the React single-page app. During development,
	Vite serves it at **http://127.0.0.1:5173** (`just web`). In production, the
	built app is served at **http://127.0.0.1:4173** by default.
- **Viewer backend** (`backend/src/revaid_ui`) — the browser-facing API for
	views/canvases and the UI's data access. It listens at
	**http://127.0.0.1:8002** by default (`just viewer`). The frontend sends its
	API requests here; users generally do not need to call it directly.

The viewer backend keeps UI view state in its own database and calls the
analysis backend over an authenticated internal HTTP API for binary/function
data. In production, expose the frontend and viewer API through one public
origin (for example, Caddy routes `/api/*` to port 8002 and other requests to
the frontend). The analysis backend should remain private.
