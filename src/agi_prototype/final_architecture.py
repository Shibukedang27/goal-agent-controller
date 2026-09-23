from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
import re

class BeliefState(str, Enum): KNOWN="KNOWN"; UNKNOWN="UNKNOWN"; LIKELY="LIKELY"; UNCERTAIN="UNCERTAIN"; CONTRADICTED="CONTRADICTED"; DISPROVEN="DISPROVEN"
@dataclass
class Belief:
    claim: str; state: BeliefState; confidence: float; provenance: list[str] = field(default_factory=list); evidence: list[str] = field(default_factory=list)
class BeliefStore:
    def __init__(self): self.items={}
    def update(self, claim, state, confidence, evidence, provenance):
        old=self.items.get(claim)
        if old and old.state != state and evidence: old.state=BeliefState.CONTRADICTED; old.confidence=min(old.confidence, confidence); old.evidence.extend(evidence); old.provenance.extend(provenance); return old
        self.items[claim]=Belief(claim,state,confidence,list(provenance),list(evidence)); return self.items[claim]

@dataclass
class WorldState:
    entities: dict = field(default_factory=dict); relationships: list = field(default_factory=list); properties: dict = field(default_factory=dict); events: list = field(default_factory=list); observations: list = field(default_factory=list); constraints: list = field(default_factory=list)
    def observe(self, observation: dict): self.observations.append(observation)
    def set_property(self, entity, key, value): self.properties.setdefault(entity,{})[key]=value

@dataclass
class Budget:
    learning: int=5; planning_depth: int=8; execution: int=3; tool_calls: int=20; runtime: int=60
    def consume(self, resource, amount=1):
        current=getattr(self,resource); setattr(self,resource,current-amount); return current >= amount
    def exhausted(self): return any(getattr(self,x)<=0 for x in ("learning","execution","tool_calls","runtime"))

PERMISSIONS={"read":"READ","write":"WRITE","run":"EXECUTE","search":"NETWORK","deploy":"DEPLOY","delete":"DELETE","credential":"CREDENTIAL/SENSITIVE"}
def permission_allowed(operation, authorized: set[str]): return PERMISSIONS.get(operation,"READ") in authorized
def redact_secrets(text): return re.sub(r"(?i)(token|secret|password|api[_-]?key)=\S+", r"\1=[REDACTED]", text)

class SelfModel:
    def __init__(self): self.capabilities={}; self.tools={}; self.failures=[]
    def update_capability(self, name, status, evidence): self.capabilities[name]={"status":status,"evidence":list(evidence)}
    def assess(self, name): return self.capabilities.get(name,{"status":"UNKNOWN","evidence":[]})
    def record_failure(self, failure): self.failures.append(failure)
