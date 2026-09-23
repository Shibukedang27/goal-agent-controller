from __future__ import annotations
from typing import Any, Literal
from pydantic import BaseModel, Field

class GoalRequest(BaseModel):
    goal: str = Field(min_length=1)
    max_learning_rounds: int = Field(default=3, ge=0, le=20)
    self_test_target: float = Field(default=100.0, ge=0, le=100)
    resources: dict[str, Any] = {}

class GoalSpec(BaseModel):
    goal: str
    success_criteria: list[str]
    constraints: list[str] = []
    deliverables: list[str] = []
    ambiguities: list[str] = []
    capabilities: list[str] = []
    artifact_type: str = "document"

class Requirement(BaseModel):
    name: str
    description: str
    required: bool = True
    parent: str | None = None
    dependencies: list[str] = []
    depth: int = 0
    confidence: float = Field(default=0.5, ge=0, le=1)
    evidence: list[str] = []
    requirement_id: str = ""
    capabilities_needed: list[str] = []

class KnowledgeItem(BaseModel):
    topic: str
    confidence: float = Field(ge=0, le=1)
    evidence: list[str] = []
    source: str = "unknown"
    test_score: float | None = Field(default=None, ge=0, le=100)
    dependencies: list[str] = []
    weaknesses: list[str] = []

class KnowledgeAudit(BaseModel):
    known: list[KnowledgeItem]
    missing: list[Requirement]

class LearningStep(BaseModel):
    topic: str
    action: str
    success_signal: str
    requirement_id: str = ""
    capability: str = ""
    evidence: list[str] = []

class TestResult(BaseModel):
    score: float = Field(ge=0, le=100)
    passed: bool
    feedback: list[str] = []
    requirement_id: str = ""
    question_or_task: str = ""
    answer_or_result: str = ""
    evidence: list[str] = []
    weaknesses: list[str] = []

class ExecutionResult(BaseModel):
    status: Literal["success", "failure"]
    output: Any = None
    observations: list[str] = []
    error: str | None = None
    artifact_type: str | None = None
    content: str | None = None
    workspace: str | None = None
    tools_used: list[str] = []
    evidence: list[dict[str, Any]] = []
    tests: list[dict[str, Any]] = []
    capabilities_used: list[str] = []
    knowledge_used: list[str] = []

class RunResult(BaseModel):
    run_id: str
    goal: GoalSpec
    requirements: list[Requirement]
    audit: KnowledgeAudit
    learning: list[LearningStep]
    self_tests: list[TestResult]
    execution: ExecutionResult | None = None
    verification: TestResult | None = None
    memory_written: bool = False
    status: Literal["ready", "executed", "failed", "blocked", "unavailable", "partial"]
    trace: list[str] = []
    failures: list[str] = []
    structured_failures: list[dict[str, Any]] = []
    attempt_history: list[dict[str, Any]] = []
    capabilities: list[dict[str, Any]] = []
    selected_tools: list[str] = []
    state: str = "COMPLETED"
    knowledge_items: list[dict[str, Any]] = []
    information_needs: list[dict[str, Any]] = []
    learning_evidence: list[dict[str, Any]] = []
    recovery_diagnostics: list[dict[str, Any]] = []
    knowledge_requirements: list[dict[str, Any]] = []
    deployment: dict[str, Any] | None = None
    learning_decision: dict[str, Any] | None = None
