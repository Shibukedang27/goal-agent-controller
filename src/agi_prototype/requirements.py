from __future__ import annotations
from dataclasses import dataclass, field

@dataclass
class KnowledgeRequirement:
    knowledge_id: str
    topic: str
    required_for: str
    status: str = "UNKNOWN"
    dependencies: list[str] = field(default_factory=list)
    information_need: str = ""
    evidence: list[str] = field(default_factory=list)

class KnowledgeRequirementGraph:
    def __init__(self, max_depth: int = 8): self.nodes={}; self.max_depth=max_depth
    def add(self, node: KnowledgeRequirement): self.nodes[node.knowledge_id] = node
    def expand(self, roots, dependencies):
        seen=set(); cycles=[]
        def visit(key, stack, depth):
            if depth > self.max_depth: return
            if key in stack: cycles.append(key); return
            if key in seen: return
            seen.add(key); node=self.nodes.setdefault(key, KnowledgeRequirement(key, key, "unknown")); node.dependencies=list(dict.fromkeys(dependencies.get(key, [])))
            for dep in node.dependencies: visit(dep, stack+[key], depth+1)
        for root in roots: visit(root, [], 0)
        return {"nodes":self.nodes, "cycles":cycles}
    def missing(self): return [x for x in self.nodes.values() if x.status in ("UNKNOWN", "MISSING", "UNVERIFIED")]
