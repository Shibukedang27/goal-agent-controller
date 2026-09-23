from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timezone

@dataclass
class Source:
    source_id: str
    source_type: str
    location: str
    authority: str
    retrieved_content: str
    extraction_method: str = "controlled practice"
    quality_evidence: list[str] = field(default_factory=list)
    title: str = ""
    retrieval_time: str = ""
    reliability: float = 0.0
    freshness: str = "unknown"
    relevance: float = 0.0
    content_type: str = "text/html"
    retrieval_method: str = ""
    metadata: dict = field(default_factory=dict)

@dataclass
class KnowledgeItem:
    knowledge_id: str
    topic: str
    claim: str
    source_id: str
    source_type: str
    source_quality: str
    evidence: list[str]
    dependencies: list[str] = field(default_factory=list)
    confidence: float = 0.0
    validation_status: str = "UNVERIFIED"
    learned_for_goal: str = ""
    tested_on: list[str] = field(default_factory=list)
    transfer_result: dict | None = None
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

@dataclass
class Contradiction:
    knowledge_ids: list[str]
    sources: list[str]
    claims: list[str]
    evidence: list[str]
    status: str = "UNRESOLVED"

class KnowledgeStore:
    def __init__(self):
        self.sources: dict[str, Source] = {}; self.items: dict[str, KnowledgeItem] = {}; self.contradictions: list[Contradiction] = []
    def discover_source(self, topic: str, allow_external: bool = False):
        if not allow_external: return None
        return None
    def add_controlled_source(self, topic: str, goal: str, evidence: str):
        sid = f"practice:{topic}"; self.sources[sid] = Source(sid, "controlled_practice", "local execution", "deterministic test", evidence, quality_evidence=["reproducible local evidence"]); return self.sources[sid]
    def extract(self, source: Source, topic: str, claim: str, goal: str):
        kid = f"knowledge:{topic}"; item = KnowledgeItem(kid, topic, claim, source.source_id, source.source_type, "controlled", [source.retrieved_content], confidence=.5, learned_for_goal=goal); self.items[kid] = item; return item
    def validate(self, item: KnowledgeItem, evidence: str, independent: bool = False):
        if evidence and (independent or item.source_type == "controlled_practice"):
            item.evidence.append(evidence); item.validation_status = "VALIDATED"; item.confidence = 1.0
        return item
    def reuse(self, topic: str, context: str):
        return next((x for x in self.items.values() if x.topic == topic and x.validation_status == "VALIDATED"), None)
    def record_contradiction(self, a: KnowledgeItem, b: KnowledgeItem):
        c = Contradiction([a.knowledge_id, b.knowledge_id], [a.source_id, b.source_id], [a.claim, b.claim], a.evidence + b.evidence); self.contradictions.append(c); return c
