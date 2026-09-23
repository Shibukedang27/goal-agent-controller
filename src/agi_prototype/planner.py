from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Callable

@dataclass
class PlanStep:
    step_id: str
    purpose: str
    required_capability: str
    selected_tool: str
    input: Any = None
    expected_output: str = ""
    verification_condition: Callable[[Any], bool] | None = None
    depends_on: list[str] = field(default_factory=list)
    condition: Callable[[dict], bool] | None = None
    alternatives: list[str] = field(default_factory=list)
    max_retries: int = 1

@dataclass
class PlanResult:
    status: str
    outputs: dict[str, Any]
    trace: list[dict]
    failures: list[dict] = field(default_factory=list)

class ToolPlanner:
    """Executes a goal-derived plan; it does not prescribe a universal tool order."""
    def execute(self, steps: list[PlanStep], handlers: dict[str, Callable[[Any, dict], Any]], max_steps: int = 20, replan: Callable[[PlanStep, Exception, dict], PlanStep | None] | None = None):
        outputs, trace, failures = {}, [], []; pending = list(steps); count = 0
        while pending and count < max_steps:
            step = pending.pop(0); count += 1
            if step.depends_on and not all(x in outputs for x in step.depends_on): pending.append(step); continue
            if step.condition and not step.condition(outputs): trace.append({"step":step.step_id,"status":"skipped","reason":"condition_false"}); continue
            value = step.input
            if isinstance(value, str) and value.startswith("$"): value = outputs.get(value[1:])
            attempts = 0; completed = False
            candidates = [step.selected_tool] + [x for x in step.alternatives if x != step.selected_tool]
            for tool in candidates:
                while attempts <= step.max_retries:
                    attempts += 1; trace.append({"step":step.step_id,"tool":tool,"status":"started","purpose":step.purpose})
                    try:
                        result = handlers[tool](value, outputs)
                        if step.verification_condition and not step.verification_condition(result): raise ValueError("intermediate_verification_failed")
                        outputs[step.step_id] = result; trace.append({"step":step.step_id,"tool":tool,"status":"verified"}); completed=True; break
                    except Exception as exc:
                        failures.append({"step":step.step_id,"tool":tool,"error":str(exc),"requirement":step.required_capability}); trace.append({"step":step.step_id,"tool":tool,"status":"failed"})
                        break
                if completed: break
            if not completed:
                replacement = replan(step, Exception(failures[-1]["error"]), outputs) if replan and failures else None
                if replacement: pending.insert(0, replacement); trace.append({"step":step.step_id,"status":"replanned"}); continue
                return PlanResult("failed", outputs, trace, failures)
        return PlanResult("completed" if not pending else "blocked", outputs, trace, failures)
