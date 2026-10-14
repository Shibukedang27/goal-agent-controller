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

## Demo

Everything below runs in mock mode, so you do not need any API keys. `MockProvider` is used whenever `OPENAI_API_KEY` is not set.

### Run it in mock mode

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
unset OPENAI_API_KEY
uvicorn agi_prototype.api:app --port 8000
```

In a second terminal:

```bash
curl -s localhost:8000/health
curl -s -X POST localhost:8000/runs \
  -H 'Content-Type: application/json' \
  -d '{"goal": "Write a short study plan for learning SQL joins", "max_learning_rounds": 2}'
```

The full `/runs` response is about 8 KB of JSON (requirements, audit, learning, self-tests, trace and more). `GET /memory` shows what the run wrote to memory.

### One-command demo

`demo.sh` starts the server, sends one goal and prints a shortened version of the response:

```bash
./demo.sh                                   # default goal
./demo.sh "Write a checklist for a code review"   # your own goal
```

### Sample output (captured from a real local run, mock mode)

```text
$ curl -s localhost:8000/health
{"status":"ok","provider":"local-rule-provider"}

$ curl -s -X POST localhost:8000/runs -d '{"goal": "Write a short study plan for learning SQL joins"}'
{
  "status": "executed",
  "state": "COMPLETED",
  "requirements": [
    "learning_objective",
    "practice_and_assessment"
  ],
  "selected_tools": [
    "artifact_writer",
    "evidence_collector"
  ],
  "artifact_type": "study_plan",
  "verification": {
    "score": 100.0,
    "passed": true
  },
  "failures": [],
  "trace_steps": 35
}

--- artifact ---
# Python Learning Plan

Goal: Write a short study plan for learning SQL joins

1. Week 1: fundamentals and exercises.
2. Week 2: functions, modules, and errors.
3. Week 3: files and testing.
4. Week 4: capstone and transfer assessment.

Evidence plan: practice tasks, tests, and review of weaknesses.
```

Note: the mock provider uses fixed templates. That is why the artifact heading says "Python Learning Plan" even though the goal is about SQL. The point of the demo is the control loop (requirements, then audit, learning, self-test, execution and verification), not the quality of the generated text. Pointing it at the OpenAI provider gives real model output.

### Recording a GIF

Option A, [vhs](https://github.com/charmbracelet/vhs). Save this as `demo.tape` and run `vhs demo.tape`:

```text
Output demo.gif
Set FontSize 16
Set Width 1100
Set Height 700
Type "./demo.sh"
Enter
Sleep 4s
```

Option B, asciinema plus agg:

```bash
asciinema rec demo.cast -c ./demo.sh
agg demo.cast demo.gif
```

## Providers

The default `MockProvider` is deterministic and credential-free. An OpenAI adapter can be selected with `OPENAI_API_KEY` and optionally `OPENAI_MODEL`. Credentials are read from environment variables and are not stored in the repository.

## Verification

The verified baseline is **68 tests passing**. Missing data, permissions, credentials, tools, or external services produce blocked or unavailable states. Generated text, a zero exit code, or model confidence alone is not considered proof of real-world success.

## Limitations

This is not AGI. Model reasoning remains a limitation. Browser access is bounded and primarily read-only; authenticated services and cloud deployment require configured connectors. Memory is lightweight, long-horizon autonomy is limited, evaluator independence is incomplete, and real-world grounding remains an open research problem.

