"""A FastAPI app that streams a pretend model's tokens.

Two endpoints answer the same question. /answer waits for every token and sends them
all together. /stream sends each token as it is produced, as server-sent events, and
stops generating when the client goes away.

    uv run uvicorn streaming_app:app --reload
    curl -N http://127.0.0.1:8000/stream
"""

import asyncio
import json
import time

from fastapi import FastAPI
from fastapi.responses import JSONResponse, StreamingResponse

TOKENS = (
    "Streaming sends each token as soon as the model produces it, so the first word "
    "arrives in milliseconds instead of seconds, and a client that leaves can stop a "
    "generation that nobody will read."
).split()
TOKEN_SECONDS = 0.05

events: list[tuple[str, int, float]] = []  # (what happened, token index, when) — for the demo

app = FastAPI()


async def generate():
    """The pretend model: one token every 50 ms. A real model's stream looks the same from here."""
    produced = -1
    try:
        for produced, token in enumerate(TOKENS):
            await asyncio.sleep(TOKEN_SECONDS)
            events.append(("generated", produced, time.perf_counter()))
            yield token + " "
    finally:
        # Runs however the loop ended: all tokens sent, or the client gone and the
        # generator closed. Either way, no more tokens are produced after this.
        events.append(("stopped", produced, time.perf_counter()))


@app.get("/health")
async def health():
    return {"ok": True}


@app.get("/answer")
async def answer():
    """The whole answer at once: nothing is sent until the last token exists."""
    text = "".join([token async for token in generate()])
    return JSONResponse({"answer": text.strip()})


@app.get("/stream")
async def stream():
    """Server-sent events: one `data:` line per token, then a sentinel."""

    async def sse():
        async for token in generate():
            yield f"data: {json.dumps(token)}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        sse(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},  # the second one tells nginx not to buffer
    )
