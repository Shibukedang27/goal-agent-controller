from __future__ import annotations
from dataclasses import dataclass

@dataclass
class Evaluation:
    passed: bool
    score: float
    evidence: list[str]
    failures: list[dict]

class IndependentEvaluator:
    """Evidence-only evaluator. It receives an artifact, never the generator's confidence."""
    def evaluate(self, goal, artifact, evidence):
        artifact_type = artifact.get("artifact_type") if isinstance(artifact, dict) else None
        expected = getattr(goal, "artifact_type", None)
        checks = [{"name":"artifact_type", "passed": artifact_type == expected, "evidence": f"expected={expected};actual={artifact_type}"}]
        checks += evidence or []
        passed = sum(1 for x in checks if x.get("passed"))
        failures = [] if passed == len(checks) else [{"failure_type":"evaluation_failure", "failed_requirement": next((x.get("name") for x in checks if not x.get("passed")), "unknown"), "evidence":[x.get("evidence", "") for x in checks if not x.get("passed")], "suspected_knowledge_gap":"specific failed requirement", "suspected_capability_gap":"specific failed operation", "evaluator_result":f"{passed}/{len(checks)} checks passed", "confidence":1.0, "recommended_next_learning_action":"study and practice the failed requirement"}]
        return Evaluation(passed == len(checks), 100 * passed / max(1, len(checks)), [x.get("evidence", "") for x in checks if x.get("passed")], failures)

