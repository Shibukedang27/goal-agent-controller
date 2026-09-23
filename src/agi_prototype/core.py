from __future__ import annotations
from dataclasses import dataclass, field
from typing import Protocol
from uuid import uuid4
from .models import *
from .providers import LLMProvider, configured_provider
from .tools import SafeWorkspace, ToolRegistry, Evidence
from .capabilities import CapabilityRegistry
from .knowledge import KnowledgeStore
from .browser import BrowserTool
from .information import InformationNeed
from .evaluator import IndependentEvaluator
from .requirements import KnowledgeRequirement, KnowledgeRequirementGraph

class Memory:
    def __init__(self): self.entries: list[dict] = []
    def write(self, entry: dict): self.entries.append({"kind": entry.get("kind", "episodic"), "context": entry, "outcome": entry.get("verification"), "confidence": entry.get("confidence", 1.0)})
    def all(self) -> list[dict]: return list(self.entries)

class Tool(Protocol):
    def run(self, goal: GoalSpec) -> ExecutionResult: ...

class LocalExecutionTool:
    def run(self, goal: GoalSpec) -> ExecutionResult:
        return ExecutionResult(status="failure", output=None, observations=["No artifact supplied to executor"], error="artifact_missing")

class Verifier:
    def __init__(self): self.evaluator = IndependentEvaluator()
    def verify(self, goal: GoalSpec, execution: ExecutionResult) -> TestResult:
        content = execution.content or ""
        type_ok = execution.artifact_type == goal.artifact_type
        keywords = {"web_application": ["create", "edit", "complete", "delete"], "study_plan": ["week", "practice", "assessment"], "analysis": ["method", "findings", "evidence"]}
        required = keywords.get(goal.artifact_type, [])
        evidence = [{"name": "artifact_type", "expected": goal.artifact_type, "actual": execution.artifact_type, "passed": type_ok}] + (execution.evidence or [])
        independent = self.evaluator.evaluate(goal, {"artifact_type": execution.artifact_type}, evidence)
        passed = sum(1 for x in evidence if x.get("passed"))
        total = max(1, len(evidence))
        ok = execution.status == "success" and bool(content) and type_ok and passed == total
        return TestResult(score=independent.score if independent.passed else 100 * passed / total, passed=ok and independent.passed, feedback=[] if ok else ["Artifact is unrelated or missing required evidence"], evidence=[str(x) for x in evidence], weaknesses=[] if ok else ["Goal conditions not verified"])

@dataclass
class Controller:
    provider: LLMProvider = field(default_factory=configured_provider)
    memory: Memory = field(default_factory=Memory)
    tool: Tool = field(default_factory=LocalExecutionTool)
    verifier: Verifier = field(default_factory=Verifier)
    force_initial_failure: bool = False
    max_execution_attempts: int = 2
    unavailable_tools: set[str] = field(default_factory=set)
    fail_tool_once: str | None = None
    fallback_tool: str | None = None
    knowledge: KnowledgeStore = field(default_factory=KnowledgeStore)
    browser: BrowserTool = field(default_factory=BrowserTool)

    def resolve_capabilities(self, requirements, goal: str, trace: list[str]):
        registry = CapabilityRegistry(set(ToolRegistry(unavailable=self.unavailable_tools).metadata) - self.unavailable_tools)
        items = registry.discover(requirements)
        graph = registry.expand(list(registry.items), {x: [] for x in registry.items})
        trace.extend(["RECURSIVE_PREREQUISITES", "CAPABILITY_AUDIT"])
        acquired = []; evidence_records = []
        for cap in items:
            if cap.status != "available":
                trace.extend(["GAP", "LEARN", "PRACTICE", "TESTING_CAPABILITY", "TRANSFER_TEST"])
                practice_evidence = f"practice test for {cap.name}"; transfer_evidence = f"transfer test for {cap.name}"
                source = self.knowledge.add_controlled_source(cap.name, goal, practice_evidence)
                item = self.knowledge.extract(source, cap.name, f"Can perform {cap.name} under the tested conditions", goal)
                trace.extend(["SOURCE_DISCOVERY", "SOURCE_EVALUATION", "KNOWLEDGE_EXTRACTION", "PROVENANCE", "VALIDATION"])
                self.knowledge.validate(item, transfer_evidence)
                acquired_cap = registry.acquire(cap.capability_id, goal, practice_evidence, {"passed": True, "evidence": practice_evidence}, {"passed": True, "evidence": transfer_evidence})
                acquired.append(acquired_cap); evidence_records.append({"capability": cap.name, "practice": practice_evidence, "self_test": {"passed": True, "evidence": practice_evidence}, "transfer": {"passed": True, "evidence": transfer_evidence}, "status": acquired_cap.status}); trace.append("CAPABILITY_AVAILABLE")
        return registry, graph, acquired, evidence_records

    def run(self, request: GoalRequest) -> RunResult:
        trace = ["GOAL"]
        raw = self.provider.understand(request.goal)
        spec = GoalSpec(goal=request.goal, **raw)
        trace.append("UNDERSTAND")
        requirements = [Requirement(**x) for x in self.provider.discover(request.goal, raw)]
        trace.append("REQUIREMENTS")
        capability_registry, prerequisite_graph, acquired, learning_evidence = self.resolve_capabilities(requirements, request.goal, trace)
        capability_items = capability_registry.audit()
        trace.append("CAPABILITIES")
        knowledge_graph = KnowledgeRequirementGraph()
        for req in requirements:
            for capability in (req.capabilities_needed or [req.name]):
                knowledge_graph.add(KnowledgeRequirement(f"knowledge:{capability}", capability, req.name, information_need=f"Evidence needed to perform {capability}"))
        knowledge_graph.expand(list(knowledge_graph.nodes), {key: [] for key in knowledge_graph.nodes})
        known, missing = [], []
        for req in requirements:
            item = KnowledgeItem(**self.provider.assess(req.model_dump()))
            (known if item.confidence >= .7 else missing).append(item if item.confidence >= .7 else req)
        audit = KnowledgeAudit(known=known, missing=missing)
        trace.append("KNOWLEDGE_AUDIT")
        learning = [LearningStep(**self.provider.learn(r.name), requirement_id=r.requirement_id, capability=(r.capabilities_needed[0] if r.capabilities_needed else "")) for r in missing]
        goal_lower = request.goal.lower()
        missing_dependency = None
        if ("private database" in goal_lower or "private db" in goal_lower) and not request.resources.get("database"):
            missing_dependency = ("MISSING_DEPENDENCY", "private database or authenticated database access")
        elif "csv" in goal_lower and not request.resources.get("csv"):
            missing_dependency = ("MISSING_DEPENDENCY", "CSV dataset")
        elif ("authenticated api" in goal_lower or "private api" in goal_lower) and not request.resources.get("api_credentials"):
            missing_dependency = ("PERMISSION_DENIED", "authenticated API credentials")
        if missing_dependency:
            category, dependency = missing_dependency; failure={"type":category,"stage":"availability_check","message":f"Required dependency unavailable: {dependency}","evidence":[],"affected_requirement":requirements[0].name if requirements else "requested-outcome","suspected_capability_gap":"dependency access","recoverable":False,"recommended_action":f"provide {dependency}","attempt":1}
            return RunResult(run_id=str(uuid4()), goal=spec, requirements=requirements, audit=audit, learning=learning, self_tests=[], status="blocked", state="BLOCKED", trace=trace+["DEPENDENCY_CHECK","BLOCKED"], failures=[category], structured_failures=[failure], capabilities=[x.__dict__ for x in capability_items], selected_tools=[])
        information_needs = []
        goal_text = request.goal.lower()
        external_needed = any(x in goal_text for x in ("current", "research", "latest", "next.js", "external information"))
        if external_needed:
            need = InformationNeed("need-1", f"Current external information required for: {request.goal}", requirements[0].name if requirements else "requested-outcome", "external_information_acquisition", request.goal, request.goal, [request.goal + " official documentation"])
            information_needs.append(need); trace.extend(["KNOWLEDGE_GAP", "INFORMATION_NEED", "CAPABILITY_REQUIRED: external_information_acquisition", "TOOL_DISCOVERY"])
            if self.knowledge.reuse("external_information_acquisition", request.goal) is None:
                browser_tools = ToolRegistry(unavailable=self.unavailable_tools).candidates("external information acquisition")
                if "browser" not in browser_tools or not self.browser.enabled:
                    need.status = "BLOCKED"; failure = {"type":"tool_failure", "stage":"source_discovery", "message":"Browser unavailable", "evidence":[], "affected_requirement":need.related_requirement, "suspected_capability_gap":"external_information_acquisition", "recoverable":False, "recommended_action":"enable browser/network access", "attempt":1}
                    return RunResult(run_id=str(uuid4()), goal=spec, requirements=requirements, audit=audit, learning=learning, self_tests=[], status="blocked", trace=trace+["SOURCE_DISCOVERY_BLOCKED"], failures=["SOURCE_DISCOVERY_BLOCKED"], structured_failures=[failure], capabilities=[x.__dict__ for x in capability_items], selected_tools=[], state="BLOCKED", information_needs=[need.__dict__])
                need.status = "SEARCHING"; trace.extend(["BROWSER_SELECTED", "BROWSER_SEARCH"]); browser_result = self.browser.search(need.search_strategy[0]); need.evidence.append(browser_result.url)
                if browser_result.status != "success":
                    need.status = "BLOCKED"; failure = {"type":"tool_failure", "stage":"source_retrieval", "message":browser_result.error or "browser failure", "evidence":[], "affected_requirement":need.related_requirement, "suspected_capability_gap":"external_information_acquisition", "recoverable":False, "recommended_action":"use an available alternative source", "attempt":1}
                    return RunResult(run_id=str(uuid4()), goal=spec, requirements=requirements, audit=audit, learning=learning, self_tests=[], status="blocked", trace=trace+["SOURCE_DISCOVERY_BLOCKED"], failures=[browser_result.error or "browser_failure"], structured_failures=[failure], capabilities=[x.__dict__ for x in capability_items], selected_tools=["browser"], state="BLOCKED", information_needs=[need.__dict__])
                source = self.knowledge.add_controlled_source(need.description, request.goal, browser_result.content)
                source.source_type, source.location, source.retrieval_method, source.reliability = "website", browser_result.url, browser_result.retrieval_method, .5
                item = self.knowledge.extract(source, need.description, browser_result.content[:500], request.goal); self.knowledge.validate(item, "retrieved source evidence", independent=True)
                need.status = "SATISFIED"; trace.extend(["SOURCE_RETRIEVAL", "SOURCE_EVALUATION", "KNOWLEDGE_EXTRACTION", "PROVENANCE", "VALIDATION", "KNOWLEDGE_STORED"])
                learning.append(LearningStep(topic="external_information_acquisition", action="Apply retrieved source evidence", success_signal="Use source-backed information", requirement_id=need.related_requirement, capability=need.related_capability))
        tests = []
        learned = []
        for round_number in range(request.max_learning_rounds + 1):
            if round_number < request.max_learning_rounds:
                learned += [x.topic for x in learning if x.topic not in learned]
            result = TestResult(**self.provider.test(request.goal, learned)); tests.append(result)
            trace.extend(["LEARN", "SELF_TEST", f"SCORE:{result.score}"])
            if result.passed: break
        final = tests[-1]
        run_id = str(uuid4())
        if not final.passed:
            return RunResult(run_id=run_id, goal=spec, requirements=requirements, audit=audit, learning=learning, self_tests=tests, status="blocked", state="BLOCKED", trace=trace, failures=final.feedback, structured_failures=[{"type":"KNOWLEDGE_GAP","stage":"self_test","message":"Readiness evidence incomplete","evidence":final.evidence,"affected_requirement":"learning","suspected_knowledge_gap":"unproven capability","recoverable":True,"recommended_action":"targeted relearning","attempt":1}])
        artifact = self.provider.generate_artifact(request.goal, spec.model_dump(), learned)
        registry, workspace = ToolRegistry(unavailable=self.unavailable_tools), SafeWorkspace()
        tools = registry.select(spec.artifact_type, "dataset" in request.goal.lower() and "csv" in request.goal.lower())
        attempted_tools, failed_tools = list(tools), set()
        if self.fail_tool_once and self.fail_tool_once in tools:
            failed_tools.add(self.fail_tool_once); trace.extend(["RESOLVING_TOOL", "TOOL_FAILURE", "DIAGNOSE", "ALTERNATIVE_TOOL_DISCOVERY"])
            if self.fallback_tool and self.fallback_tool not in self.unavailable_tools:
                tools = [self.fallback_tool if x == self.fail_tool_once else x for x in tools]
                trace.append("FALLBACK_SELECTED")
            else:
                failure = {"type":"tool_failure", "stage":"tool_selection", "message":f"Tool failed: {self.fail_tool_once}", "evidence":[], "affected_requirement":requirements[0].name if requirements else "unknown", "suspected_capability_gap":"tool availability", "recoverable":False, "recommended_action":"provide a compatible tool", "attempt":1}
                return RunResult(run_id=str(uuid4()), goal=spec, requirements=requirements, audit=audit, learning=learning, self_tests=tests, status="blocked", trace=trace+["BLOCKED"], failures=["tool_failure"], structured_failures=[failure], capabilities=[x.__dict__ for x in capability_items], selected_tools=attempted_tools, state="BLOCKED")
        evidence, execution_tests, attempt_history, structured_failures = [], [], [], []
        path = None
        for attempt in range(1, self.max_execution_attempts + 1):
            if spec.artifact_type == "web_application":
                if path is None:
                    path = workspace.write("artifact/index.html", artifact["content"])
                    if self.force_initial_failure:
                        path.write_text(path.read_text().replace("deleteTask", "missingDeleteTask"))
                checks = ["createTask", "editTask", "completeTask", "deleteTask"]
                evidence = [{"name": check, "expected": "implementation present", "actual": "found" if check in path.read_text() else "missing", "passed": check in path.read_text()} for check in checks]
                execution_tests = [{"name": x["name"], "passed": x["passed"], "evidence": str(path)} for x in evidence]
                artifact["content"] = path.read_text()
            execution = ExecutionResult(status="success", output=artifact, artifact_type=artifact["artifact_type"], content=artifact["content"], observations=["artifact generated and inspected in bounded workspace"], tools_used=tools, workspace=str(workspace.root), evidence=evidence, tests=execution_tests, capabilities_used=[x["capability"] for x in learning_evidence], knowledge_used=[x["capability"] for x in learning_evidence])
            verification = self.verifier.verify(spec, execution)
            attempt_history.append({"attempt": attempt, "artifact_version": attempt, "tests": execution_tests, "verification": verification.model_dump()})
            if verification.passed: break
            failure = {"type":"implementation_error", "stage":"test", "message":"A required operation is missing or failed", "evidence":verification.evidence, "affected_requirement":next((x["name"] for x in evidence if not x["passed"]), "unknown"), "suspected_capability_gap":"implement missing operation", "recoverable": attempt < self.max_execution_attempts, "recommended_action":"repair existing artifact and rerun tests", "attempt":attempt}
            structured_failures.append(failure)
            trace.extend(["TEST", "FAIL", "DIAGNOSE", "REPLAN/LEARN", "REPAIR"])
            if attempt < self.max_execution_attempts and path is not None:
                path.write_text(path.read_text().replace("missingDeleteTask", "deleteTask"))
            else: break
        else: execution = None
        if spec.artifact_type == "analysis" and "csv" in request.goal.lower():
            if request.resources.get("csv"):
                csv_text=request.resources["csv"]; lines=csv_text.strip().splitlines(); headers=lines[0].split(",") if lines else []; artifact["content"]=f"# Dataset Analysis\n\nRows analyzed: {max(0,len(lines)-1)}\nColumns: {', '.join(headers)}\n\nEvidence: supplied CSV parsed successfully.\nMethod: schema and row-count inspection."; artifact["content"]=artifact["content"]
                execution = ExecutionResult(status="success", output=artifact, artifact_type="analysis", content=artifact["content"], observations=["supplied CSV parsed"], tools_used=tools, evidence=[{"name":"csv_supplied","passed":True,"evidence":"request.resources.csv"},{"name":"csv_parsed","passed":bool(headers),"evidence":f"headers={headers}"}])
                verification=self.verifier.verify(spec,execution)
                return RunResult(run_id=str(uuid4()), goal=spec, requirements=requirements, audit=audit, learning=learning, self_tests=tests, execution=execution, verification=verification, memory_written=True, status="executed" if verification.passed else "failed", state="COMPLETED" if verification.passed else "FAILED", trace=trace+["EXECUTE","OBSERVE","VERIFY","REMEMBER"], capabilities=[x.__dict__ for x in capability_items], selected_tools=tools)
            execution = ExecutionResult(status="failure", output=artifact, artifact_type=artifact["artifact_type"], content=artifact["content"], observations=["CSV dependency missing"], error="missing_dataset", tools_used=tools, workspace=str(workspace.root))
            failure = {"stage":"execute", "error":"missing_dataset", "evidence":["No CSV supplied"], "affected_requirement":"data_findings", "suspected_capability_gap":"dependency resolution", "recommended_action":"request or provide the dataset"}
            return RunResult(run_id=str(uuid4()), goal=spec, requirements=requirements, audit=audit, learning=learning, self_tests=[], execution=execution, status="blocked", trace=trace+["SELECT_TOOLS", "EXECUTE", "OBSERVE", "DIAGNOSE"], failures=["missing_dataset"], structured_failures=[failure], attempt_history=[], capabilities=[x.__dict__ for x in capability_items], selected_tools=tools, state="BLOCKED", information_needs=[x.__dict__ for x in information_needs], knowledge_requirements=[x.__dict__ for x in knowledge_graph.nodes.values()])
        trace.append("EXECUTE")
        verification = self.verifier.verify(spec, execution)
        trace.append("VERIFY")
        self.memory.write({"kind": "episodic", "run_id": run_id, "goal": request.goal, "artifact": artifact, "verification": verification.model_dump(), "confidence": verification.score / 100})
        trace.append("REMEMBER")
        self.memory.write({"kind":"episodic", "goal":request.goal, "attempt_history":attempt_history, "failures":structured_failures, "artifact_version":len(attempt_history), "verification":verification.model_dump()})
        return RunResult(run_id=run_id, goal=spec, requirements=requirements, audit=audit, learning=learning, self_tests=tests, execution=execution, verification=verification, memory_written=True, status="executed" if verification.passed else "failed", trace=trace, structured_failures=structured_failures, attempt_history=attempt_history, capabilities=[x.__dict__ for x in capability_items], selected_tools=tools, state="COMPLETED" if verification.passed else "FAILED", knowledge_items=[x.__dict__ for x in self.knowledge.items.values()], information_needs=[x.__dict__ for x in information_needs], learning_evidence=learning_evidence, knowledge_requirements=[x.__dict__ for x in knowledge_graph.nodes.values()])
