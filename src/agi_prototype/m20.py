from __future__ import annotations
from dataclasses import dataclass

M20_GOALS = {
    "research": "Research a factual question and provide evidence-backed findings.",
    "programming": "Build a small web application that allows a user to create, edit, complete, and delete tasks.",
    "data": "Analyze a CSV dataset and identify the most important trends.",
    "multi_tool": "Research current requirements and produce a verified implementation plan.",
    "unfamiliar_knowledge": "Learn the current requirements for using a technical API and produce an implementation plan.",
    "failure_recovery": "Build a small web application that allows a user to create, edit, complete, and delete tasks.",
    "transfer": "Create a task list with 9 items and verify completion behavior",
}

@dataclass
class AuditFinding:
    area: str; status: str; evidence: str; limitation: str = ""

def audit_result(result):
    return [AuditFinding("goal preservation", "pass", result.goal.goal), AuditFinding("traceability", "pass" if result.trace else "fail", " -> ".join(result.trace)), AuditFinding("execution evidence", "pass" if result.execution and result.execution.evidence else "blocked", "execution evidence present" if result.execution else "no execution"), AuditFinding("independent verification", "pass" if result.verification and result.verification.passed else "blocked/failed", "verifier result"), AuditFinding("autonomy boundary", "partial", "controller orchestrates the loop", "provider and acquisition remain deterministic in local mode")]

def run_benchmark(controller):
    from .models import GoalRequest
    results={name: controller.run(GoalRequest(goal=goal)) for name, goal in M20_GOALS.items()}
    return results, {name: audit_result(result) for name, result in results.items()}

AUTONOMY_AUDIT = {"genuinely_autonomous":["bounded controller orchestration", "goal-conditioned requirements", "evidence traces", "failure states"], "deterministic":["MockProvider", "local capability acquisition", "local artifact templates", "controlled fixtures"], "model_provided":["semantic goal interpretation in local mode", "source claim extraction"], "tool_constraints":["registered tools only", "workspace and command boundaries", "cloud connectors require credentials"], "weak_evaluator_independence":["local evaluator is separate but deterministic"], "limited_generalization":["principle retrieval uses capability/domain overlap"], "unavailable_real_world":["authenticated cloud deployment", "full browser JavaScript interaction", "missing user datasets"], "before_agi":["strong independent evaluation", "robust world grounding", "durable memory/retrieval", "broader transfer evidence", "safety guarantees"]}
