from dataclasses import dataclass, field

@dataclass
class InformationNeed:
    information_need_id: str
    description: str
    related_requirement: str
    related_capability: str
    knowledge_gap: str
    required_for_goal: str
    search_strategy: list[str]
    priority: int = 1
    status: str = "DISCOVERED"
    evidence: list[str] = field(default_factory=list)
