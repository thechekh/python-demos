# python-demos

The Python demos behind the articles on [chekh.dev](https://chekh.dev): small, runnable
programs that show one idea each, with tests, and the scripts that produce every number
and chart the articles quote.

| Files | Article | What it does |
|---|---|---|
| `asyncio_demo.py` | [asyncio from the ground up](https://chekh.dev/writing/asyncio-from-the-ground-up/) | Ten pretend downloads sequentially, concurrently and bounded; ten computations in coroutines, threads and processes; a heartbeat that shows when the loop is blocked |
| `streaming_app.py`, `streaming_demo.py` | [Streaming output through FastAPI](https://chekh.dev/writing/streaming-output-through-fastapi/) | A FastAPI app streaming a pretend model's tokens as server-sent events, played against five kinds of client |
| `contracts_models.py`, `contracts_model.py`, `contracts_demo.py` | [Pydantic v2 as the contract between code and model](https://chekh.dev/writing/pydantic-v2-as-the-contract-between-code-and-model/) | An invoice contract, a scripted extractor that makes realistic mistakes, and a validate-and-retry loop over 200 documents |

## Run it

Needs Python 3.12 and [uv](https://docs.astral.sh/uv/). No accounts, no keys: the
"models" are scripts that stand in for one.

```sh
git clone https://github.com/thechekh/python-demos
cd python-demos
uv sync
uv run pytest                      # every demo's tests
uv run python asyncio_demo.py      # or streaming_demo.py, contracts_demo.py
```

Each demo prints its numbers, writes them to `results/<slug>.json`, and draws its charts
into `charts/<slug>/`; `--charts-only` redraws from the saved numbers.

To see the streaming app by hand:

```sh
uv run uvicorn streaming_app:app
curl -N http://127.0.0.1:8000/stream     # tokens arrive one by one
curl http://127.0.0.1:8000/answer        # everything at once, after a wait
```

## Change something

- `asyncio_demo.py` — change `LIMIT`, `TASKS` or `CPU_LOOPS`; add a schedule and it
  joins the timeline
- `streaming_app.py` — replace `generate()` with a real model's stream: anything that
  yields strings works, and the cancellation still does
- `contracts_models.py` — add a field to `Invoice`; the schema, the validation and the
  retry loop pick it up without other changes. `contracts_model.py` has the mistake rates

## Licence

MIT, see `LICENSE`. The Lora font files in `fonts/` are under the SIL Open Font License.
