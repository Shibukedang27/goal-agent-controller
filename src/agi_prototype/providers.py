from __future__ import annotations
from typing import Protocol
import json, os, urllib.request

class LLMProvider(Protocol):
    def understand(self, goal: str) -> dict: ...
    def discover(self, goal: str, spec: dict) -> list[dict]: ...
    def assess(self, requirement: dict) -> dict: ...
    def learn(self, topic: str) -> dict: ...
    def test(self, goal: str, learned_topics: list[str]) -> dict: ...
    def generate_artifact(self, goal: str, spec: dict, learned_topics: list[str]) -> dict: ...

ModelProvider = LLMProvider

class MockProvider:
    """Deterministic fallback; replace with an LLM adapter without changing modules."""
    def understand(self, goal: str) -> dict:
        text = goal.lower()
        if any(x in text for x in ("web application", "website", "app")):
            kind = "web_application"
        elif any(x in text for x in ("learn", "learning plan", "study", "four-week plan")):
            kind = "study_plan"
        elif any(x in text for x in ("analyze", "analyse", "dataset", "csv", "trends")):
            kind = "analysis"
        else:
            kind = "document"
        return {"success_criteria": [f"The {kind} artifact directly satisfies the requested outcome", "The artifact contains evidence that each functional requirement is addressed"], "constraints": [], "deliverables": [kind], "ambiguities": ["Detailed audience and implementation constraints are unspecified"], "capabilities": ["requirements analysis", "artifact generation", "verification"], "artifact_type": kind}

    def discover(self, goal: str, spec: dict) -> list[dict]:
        text = goal.lower()
        if "web application" in text or "website" in text or "app" in text:
            return [{"requirement_id":"functional-interaction", "name":"functional_interaction", "description":"The application supports the user actions explicitly requested", "confidence":.3, "capabilities_needed":["web UI implementation", "state management"]}, {"requirement_id":"validation", "name":"validation", "description":"Inputs and state transitions are handled safely", "confidence":.3, "capabilities_needed":["input validation"]}, {"requirement_id":"testability", "name":"testability", "description":"The requested behavior can be tested", "confidence":.3, "capabilities_needed":["software testing"]}]
        if any(x in text for x in ("learn", "learning plan", "study", "four-week plan")):
            return [{"requirement_id":"learning-objective", "name":"learning_objective", "description":"The plan progresses from the stated starting level toward the requested learning outcome", "confidence":.3, "capabilities_needed":["curriculum design"]}, {"requirement_id":"practice-and-assessment", "name":"practice_and_assessment", "description":"The plan includes practice and measurable assessment", "confidence":.3, "capabilities_needed":["assessment design"]}]
        if any(x in text for x in ("analyze", "analyse", "dataset", "csv", "trends")):
            return [{"requirement_id":"data-findings", "name":"data_findings", "description":"The analysis identifies important trends supported by data", "confidence":.3, "capabilities_needed":["data analysis"]}, {"requirement_id":"evidence", "name":"evidence", "description":"Findings include methodology and evidence", "confidence":.3, "capabilities_needed":["statistical reasoning"]}]
        return [{"requirement_id":"requested-outcome", "name":"requested_outcome", "description":"The artifact directly addresses the user's requested outcome", "confidence":.3, "capabilities_needed":["requirements analysis"]}]

    def assess(self, requirement: dict) -> dict:
        return {"topic": requirement["name"], "confidence": requirement.get("confidence", .3), "evidence": [], "source": "mock", "weaknesses": ["No demonstrated capability yet"], "dependencies": requirement.get("capabilities_needed", [])}

    def learn(self, topic: str) -> dict:
        return {"topic": topic, "action": f"Practice the capability required for {topic}", "success_signal": f"Produce evidence addressing {topic}"}

    def test(self, goal: str, learned_topics: list[str]) -> dict:
        score = min(100.0, len(learned_topics) * 50.0)
        return {"score": score, "passed": score >= 100, "feedback": [] if score >= 100 else ["Capability evidence is incomplete"], "question_or_task": "Demonstrate each discovered requirement", "answer_or_result": str(learned_topics), "evidence": [f"Practiced capability: {x}" for x in learned_topics], "weaknesses": [] if score >= 100 else ["Unproven requirement coverage"]}

    def generate_artifact(self, goal: str, spec: dict, learned_topics: list[str]) -> dict:
        kind = spec.get("artifact_type", "document")
        if kind == "study_plan": content = f"# Python Learning Plan\n\nGoal: {goal}\n\n1. Week 1: fundamentals and exercises.\n2. Week 2: functions, modules, and errors.\n3. Week 3: files and testing.\n4. Week 4: capstone and transfer assessment.\n\nEvidence plan: practice tasks, tests, and review of weaknesses."
        elif kind == "web_application": content = """<!doctype html><html><body><h1>Tasks</h1><input id='task'><button onclick='createTask()'>Create</button><ul id='tasks'></ul><script>
let tasks=[]; function render(){document.querySelector('#tasks').innerHTML=tasks.map((t,i)=>`<li data-id='${i}'><span>${t.text}</span><button onclick='editTask(${i})'>Edit</button><button onclick='completeTask(${i})'>Complete</button><button onclick='deleteTask(${i})'>Delete</button></li>`).join('')}
function createTask(){const e=document.querySelector('#task');if(e.value.trim()){tasks.push({text:e.value,done:false});e.value='';render()}} function editTask(i){const v=prompt('Edit task',tasks[i].text);if(v&&v.trim()){tasks[i].text=v;render()}} function completeTask(i){tasks[i].done=true;render()} function deleteTask(i){tasks.splice(i,1);render()} render();</script></body></html>"""
        elif kind == "analysis": content = f"# Dataset Analysis\n\nGoal: {goal}\n\n## Method\nInspect schema, clean missing values, summarize distributions, and compare trends.\n\n## Findings\nNo CSV was supplied, so no factual trend can be claimed. The analysis is blocked pending the dataset.\n\n## Evidence\nInput dataset: missing."
        else: content = f"# Requested Artifact\n\nGoal: {goal}\n\nThis artifact addresses the requested outcome and lists the verification approach."
        return {"artifact_type": kind, "content": content}

class OpenAIProvider:
    """Minimal JSON-mode adapter. It is only selected when OPENAI_API_KEY exists."""
    def __init__(self, api_key: str | None = None, model: str | None = None):
        self.api_key, self.model = api_key or os.getenv("OPENAI_API_KEY"), model or os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        if not self.api_key: raise ValueError("OPENAI_API_KEY is not configured")
    def _json(self, instruction: str) -> dict:
        body = json.dumps({"model": self.model, "response_format": {"type": "json_object"}, "messages": [{"role": "user", "content": instruction}]}).encode()
        req = urllib.request.Request("https://api.openai.com/v1/chat/completions", body, {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=60) as response: return json.loads(json.loads(response.read())["choices"][0]["message"]["content"])
    def understand(self, goal): return self._json(f"Understand this goal and return JSON keys success_criteria, constraints, deliverables, ambiguities, capabilities: {goal}")
    def discover(self, goal, spec): return self._json(f"Return a JSON array of dynamic requirements for this goal, each with name, description, confidence: {goal}")["requirements"]
    def assess(self, requirement): return self._json(f"Audit current capability for this requirement and return topic, confidence, evidence, source, weaknesses: {requirement}")
    def learn(self, topic): return self._json(f"Create one learning step for {topic}: return topic, action, success_signal")
    def test(self, goal, learned_topics): return self._json(f"Evaluate readiness for {goal} after learning {learned_topics}; return score 0-100, passed boolean, feedback list")
    def generate_artifact(self, goal, spec, learned_topics): return self._json(f"Create the actual artifact for this goal as JSON with artifact_type and content: {goal}")

def configured_provider() -> LLMProvider:
    if os.getenv("OPENAI_API_KEY"):
        try: return OpenAIProvider()
        except Exception: pass
    return MockProvider()

LocalRuleProvider = MockProvider
