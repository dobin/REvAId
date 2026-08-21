# Implementing a real adapter (M1 handoff)

GraphRev's Ghidra and LLM integrations are `Protocol`s (TAD §6.3). M0 ships
only mock implementations; this document is the contract a real adapter must
satisfy, so M1 (`I12`, `I13`) can be implemented with zero changes to
`services/`, `repositories/`, or the API surface.

> Status: this file is a stub in M1 (project setup). It will be filled in
> when `adapters/ghidra/base.py` and `adapters/llm/base.py` are implemented
> in Increments I2 and I7 respectively.

## Ghidra adapter

Implement `graphrev.adapters.ghidra.base.GhidraAdapter`:

```python
class GhidraAdapter(Protocol):
    def list_binaries(self) -> Sequence[RawBinary]: ...
    def iter_functions(self, binary: RawBinaryRef) -> Iterator[RawFunction]: ...
    def iter_edges(self, binary: RawBinaryRef) -> Iterator[RawEdge]: ...
    def get_function(self, binary: RawBinaryRef, address: int) -> RawFunction | None: ...
```

## LLM adapter

Implement `graphrev.adapters.llm.base.LlmAdapter`:

```python
class LlmAdapter(Protocol):
    async def summarize(self, req: SummaryRequest) -> SummaryResult: ...
```

Map every provider error onto the `SummarizationError` taxonomy
(`TransientProviderError`, `RateLimitError`, `AuthError`,
`ContextTooLargeError`, `PermanentProviderError`) — the worker's
retry/backoff policy is driven entirely by these types.

Prompt content is explicitly out of scope for GraphRev's own architecture
(PRD `AS14`); `summarization/context.py` assembles the `SummaryRequest`, and
what a real adapter does with it (system prompt, model choice, truncation
strategy, prompt-injection fencing for untrusted binary content) is
adapter-owned.
