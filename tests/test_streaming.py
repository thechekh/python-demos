"""The app's endpoints in-process, with no network and no waiting."""

import pytest
from httpx import ASGITransport, AsyncClient

import streaming_app


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture(autouse=True)
def fast_tokens(monkeypatch):
    monkeypatch.setattr(streaming_app, "TOKEN_SECONDS", 0)
    streaming_app.events.clear()


@pytest.mark.anyio
async def test_answer_returns_the_whole_text():
    async with AsyncClient(transport=ASGITransport(app=streaming_app.app), base_url="http://test") as client:
        response = await client.get("/answer")
    assert response.json()["answer"].split() == streaming_app.TOKENS


@pytest.mark.anyio
async def test_stream_sends_one_event_per_token_then_done():
    async with AsyncClient(transport=ASGITransport(app=streaming_app.app), base_url="http://test") as client:
        response = await client.get("/stream")
    assert response.headers["content-type"].startswith("text/event-stream")
    events = [line for line in response.text.split("\n") if line.startswith("data: ")]
    assert len(events) == len(streaming_app.TOKENS) + 1
    assert events[-1] == "data: [DONE]"


@pytest.mark.anyio
async def test_closing_the_generator_stops_generation():
    gen = streaming_app.generate()
    received = [await anext(gen) for _ in range(3)]
    await gen.aclose()  # what happens when the client goes away
    assert len(received) == 3
    assert ("stopped", 2, pytest.approx(streaming_app.events[-1][2])) == streaming_app.events[-1]
    assert sum(1 for kind, _, _ in streaming_app.events if kind == "generated") == 3
