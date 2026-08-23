Build a web application for reverse-engineering software binaries using a semantic function graph. 

Based on a function name or memory address, show boxes of functions reversed (disassembled / decompiled by ghidra)
from a exe. For example to explore the functions of a callstack, and see which sub-functions each function calls,
and if there are other callers to it. like a graph. But instead of showing assembly or decompiled C code, just show function names
and two LLM generated summaries. One short one, and more about the details of what the function is doing. 

Or in other words, instead of basic blocks, show functions names with LLM summary.

In the db, each function should store: 
* inherent information
  * address (memory address)
  * assembly (asm)
  * its c code (disassembled)
  * function name 
  * parameters
* AI / LLM
  * function llm summary short
  * function llm summary long
* ui
  * color (of the background)
  * visible (default false)
  * collapsed (show smaller in ui)
  * position x/y

I also need a script which will use Ghidra to populate functions (with address, assembly, c code, function name, parameters) and edges
in the sqlite DB. 

Access to Ghidra via REST and Agent which does the analyzing can be mocked right now, and will be implemented later. 
I want to check the basic UI functionality first. 


## Implementation Idea

### Core Tech Stack
- Frontend: React with React Flow and ELK.js for positioning
- Backend: Python (FastAPI), uv
- Database: SQLite (via SQLAlchemy).
- Integrations: 
  1. Ghidra (via Model Context Protocol - MCP or REST API/Bridge).
  2. LLM Provider (Anthropic API / OpenAI API).

### Database Schema (SQLite)
Create tables to store function summaries locally so expensive LLM calls are cached:
- `binaries` (id, name, version)
- `functions` (id, binary_id, see above)
- `edges` (id, caller_id, callee_id)

### On-Demand LLM Summarization Workflow
* When a function card is displayed, it should show its name and llm summary from the backend 
* If the data does not exist, it should be generated immediately at runtime 

### Graph UI
- Node Display: Render nodes as card-like elements displaying function name, llm summary_short, and maybe some other things
- Lazy Load Edges: Do not load the entire binary graph at once. Load the selected root node and its immediate 1-hop callers and callees. Show an "+ Expand" action on nodes to load 1 step deeper.
- Visual States:
  - Greyed/Neutral Node: Not yet summarized.
  - Highlighted Node: Has cached LLM summary.
  - Loading State: LLM is actively analyzing pseudocode.
- It should be possible for the user to paste a callstack, so like 10 functions calling each other

I currently dont have much use for ASM/C code, but still store it in the DB. 