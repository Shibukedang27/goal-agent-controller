from __future__ import annotations
from dataclasses import dataclass, field

@dataclass
class Capability:
    capability_id: str
    name: str
    description: str
    status: str = "unknown"
    confidence: float = 0.0
    evidence: list[str] = field(default_factory=list)
    required_tools: list[str] = field(default_factory=list)
    prerequisites: list[str] = field(default_factory=list)
    verification_method: str = "independent test"
    learned_from: list[str] = field(default_factory=list)
    last_test_result: dict | None = None

class CapabilityRegistry:
    def __init__(self, available_tools: set[str] | None = None):
        self.available_tools = available_tools or {"filesystem", "code_execution", "test_runner", "artifact_writer", "evidence_collector", "data_analysis", "dependency_inspector", "browser"}
        self.items: dict[str, Capability] = {}
    def discover(self, requirements):
        for req in requirements:
            for name in req.capabilities_needed:
                cid = name.replace(" ", "_")
                self.items.setdefault(cid, Capability(cid, name, f"Capability required for {req.name}", required_tools=["code_execution" if "implement" in name or "web" in name else "artifact_writer"]))
        return list(self.items.values())
    def audit(self):
        for cap in self.items.values():
            tools_ok = all(t in self.available_tools for t in cap.required_tools)
            if tools_ok and cap.evidence: cap.status, cap.confidence = "available", 1.0
            elif tools_ok: cap.status, cap.confidence = "partially_available", .3
            else: cap.status, cap.confidence = "missing", 0.0
        return list(self.items.values())
    def acquire_with_evidence(self, cap_id: str, evidence: str):
        cap = self.items[cap_id]; cap.evidence.append(evidence); cap.status = "available"; cap.confidence = 1.0; cap.last_test_result = {"passed": True, "evidence": evidence}; return cap
    def prerequisite_graph(self): return {k: v.prerequisites for k, v in self.items.items()}
    def expand(self, roots: list[str], prerequisite_map: dict[str, list[str]], max_depth: int = 8):
        """Expand a bounded dependency graph; cycles are reported, never recursed forever."""
        graph, visiting, expanded, cycles = {}, set(), set(), []
        def visit(node: str, depth: int):
            if depth > max_depth: graph.setdefault(node, []); return
            if node in visiting: cycles.append(node); return
            if node in expanded: return
            visiting.add(node); deps = list(dict.fromkeys(prerequisite_map.get(node, []))); graph[node] = deps
            for dep in deps: visit(dep, depth + 1)
            visiting.remove(node); expanded.add(node)
        for root in roots: visit(root, 0)
        return {"graph": graph, "cycles": cycles, "max_depth": max_depth}
    def acquire(self, cap_id: str, goal: str, practice: str, test: dict, transfer: dict):
        cap = self.items[cap_id]
        cap.learned_from.append(goal); cap.last_test_result = {"practice": practice, "test": test, "transfer": transfer}
        if test.get("passed") and transfer.get("passed"):
            cap.evidence.extend([test.get("evidence", ""), transfer.get("evidence", "")]); cap.status, cap.confidence = "available", 1.0
        else: cap.status, cap.confidence = "partially_available", max(cap.confidence, .5)
        return cap
