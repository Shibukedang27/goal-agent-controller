# AGI Bro

AGI Bro is an AGI-oriented research prototype exploring how a system can turn a user’s goal into a bounded, evidence-driven execution process. It is not AGI.

The core idea: **the user provides the WHAT; the system determines the HOW.**

The controller discovers requirements and capabilities, audits knowledge, researches through a bounded browser, learns and practices, tests and transfers capabilities, selects tools, executes artifacts, verifies observed results, diagnoses failures, retries within limits, records memory, and generalizes experience.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
pytest
uvicorn agi_prototype.api:app --reload
```

Open `http://127.0.0.1:8000/docs` and submit a goal to `POST /runs`.

## Providers

The default `MockProvider` is deterministic and credential-free. An OpenAI adapter can be selected with `OPENAI_API_KEY` and optionally `OPENAI_MODEL`. Credentials are read from environment variables and are not stored in the repository.

## Verification

The verified baseline is **68 tests passing**. Missing data, permissions, credentials, tools, or external services produce blocked or unavailable states. Generated text, a zero exit code, or model confidence alone is not considered proof of real-world success.

## Limitations

This is not AGI. Model reasoning remains a limitation. Browser access is bounded and primarily read-only; authenticated services and cloud deployment require configured connectors. Memory is lightweight, long-horizon autonomy is limited, evaluator independence is incomplete, and real-world grounding remains an open research problem.

