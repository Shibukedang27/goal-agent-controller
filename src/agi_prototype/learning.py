from __future__ import annotations
from dataclasses import dataclass, field

@dataclass
class LearningObjective:
    objective_id: str
    topic: str
    goal_relevance: float
    uncertainty: float
    usefulness: float
    dependencies: list[str] = field(default_factory=list)
    evidence_required: list[str] = field(default_factory=list)
    status: str = "UNKNOWN"

@dataclass
class LearningDecision:
    ordered_objectives: list[str]
    next_objective: str | None
    practice_task: str | None
    independent_test: str | None
    transfer_test: str | None
    ready: bool
    stop_reason: str
    budget_used: int

class AdaptiveLearningPlanner:
    def __init__(self, budget: int = 5): self.budget=budget; self.objectives={}; self.history=[]
    def derive(self, requirements, audit):
        for req in requirements:
            for i, capability in enumerate(req.capabilities_needed or [req.name]):
                key=f"{req.requirement_id}:{i}"; self.objectives[key]=LearningObjective(key, capability, 1.0 if req.required else .5, .7, .8, evidence_required=[f"independent test for {capability}", f"transfer test for {capability}"])
        return list(self.objectives.values())
    def split(self, objective_id: str, parts: list[str]):
        parent=self.objectives[objective_id]
        for i, part in enumerate(parts): self.objectives[f"{objective_id}.{i}"]=LearningObjective(f"{objective_id}.{i}",part,parent.goal_relevance,parent.uncertainty,parent.usefulness,[objective_id],parent.evidence_required)
        parent.status="decomposed"; return [x for x in self.objectives.values() if x.dependencies == [objective_id]]
    def decide(self) -> LearningDecision:
        unknown=[x for x in self.objectives.values() if x.status not in ("available", "decomposed")]
        ordered=sorted(unknown,key=lambda x:(-len([d for d in x.dependencies if self.objectives.get(d, x).status != "available"]), -(x.goal_relevance+x.uncertainty+x.usefulness)))
        if not ordered: return LearningDecision([],None,None,None,None,True,"all objectives have evidence",len(self.history))
        if len(self.history)>=self.budget: return LearningDecision([x.objective_id for x in ordered],None,None,None,None,False,"learning budget exhausted",len(self.history))
        x=ordered[0]; return LearningDecision([z.objective_id for z in ordered],x.objective_id,f"Practice: apply {x.topic} to a controlled task",f"Independently test {x.topic}",f"Apply {x.topic} to a novel task",False,"evidence still required",len(self.history))
    def record(self, objective_id: str, practice: bool, independent: bool, transfer: bool):
        x=self.objectives[objective_id]; self.history.append({"objective":objective_id,"practice":practice,"independent":independent,"transfer":transfer}); x.status="available" if practice and independent and transfer else "needs_relearning"; return x
