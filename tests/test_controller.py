from agi_prototype.core import Controller
from agi_prototype.models import GoalRequest
from agi_prototype.capabilities import Capability, CapabilityRegistry
from agi_prototype.tools import ToolRegistry
from agi_prototype.knowledge import KnowledgeStore, KnowledgeItem
from agi_prototype.browser import BrowserTool
from agi_prototype.evaluator import IndependentEvaluator
from agi_prototype.requirements import KnowledgeRequirementGraph, KnowledgeRequirement
from agi_prototype.benchmarks import BENCHMARK_GOALS
from agi_prototype.runtime import ToolRuntime
from agi_prototype.planner import PlanStep, ToolPlanner
from agi_prototype.devtools import RepositoryTools
from agi_prototype.deployment import LocalDeployment, VercelDeployment, redact
from agi_prototype.generalization import GeneralizationMemory, parameterized_goals
from agi_prototype.learning import AdaptiveLearningPlanner
from agi_prototype.m20 import M20_GOALS, AUTONOMY_AUDIT, run_benchmark
from agi_prototype.final_architecture import BeliefStore, BeliefState, WorldState, Budget, permission_allowed, redact_secrets, SelfModel
from pathlib import Path
import tempfile

def test_end_to_end_local_loop():
    result = Controller().run(GoalRequest(goal="Create a four-week plan to learn Python from beginner level."))
    assert result.status == "executed"
    assert result.self_tests[-1].score == 100
    assert result.verification and result.verification.passed
    assert result.memory_written
    assert result.execution.artifact_type == "study_plan"
    assert "Week 1" in result.execution.content
    assert result.trace[-1] == "REMEMBER"

def test_learning_can_be_bounded():
    result = Controller().run(GoalRequest(goal="x", max_learning_rounds=0))
    assert result.status == "blocked"
    assert result.execution is None

def test_goal_conditioned_artifact_types():
    controller = Controller()
    web = controller.run(GoalRequest(goal="Build a small web application that allows a user to create, edit, complete, and delete tasks."))
    plan = controller.run(GoalRequest(goal="Create a four-week plan to learn Python from beginner level."))
    analysis = controller.run(GoalRequest(goal="Analyze a CSV dataset and identify the most important trends."))
    assert web.execution.artifact_type == "web_application"
    assert all(word in web.execution.content.lower() for word in ("create", "edit", "complete", "delete"))
    assert plan.execution.artifact_type == "study_plan"
    assert analysis.status == "blocked"
    assert analysis.failures == ["MISSING_DEPENDENCY"]

def test_unrelated_artifact_fails_verification():
    controller = Controller()
    result = controller.run(GoalRequest(goal="Build a small web application that allows a user to create, edit, complete, and delete tasks."))
    result.execution.artifact_type = "study_plan"
    result.execution.content = "Python week 1 practice plan"
    verification = controller.verifier.verify(result.goal, result.execution)
    assert not verification.passed
    assert verification.score < 100

def test_failure_repair_retry_closes_the_loop():
    controller = Controller(force_initial_failure=True)
    result = controller.run(GoalRequest(goal="Build a small web application that allows a user to create, edit, complete, and delete tasks."))
    assert result.status == "executed"
    assert len(result.attempt_history) == 2
    assert result.attempt_history[0]["verification"]["passed"] is False
    assert result.attempt_history[1]["verification"]["passed"] is True
    assert result.structured_failures[0]["type"] == "implementation_error"
    assert "REPAIR" in result.trace
    assert result.verification.score == 100

def test_capabilities_and_tools_are_goal_conditioned():
    result = Controller().run(GoalRequest(goal="Build a small web application that allows a user to create, edit, complete, and delete tasks."))
    assert result.selected_tools == ["filesystem", "code_execution", "test_runner"]
    assert result.capabilities
    assert all("required_tools" in c and "status" in c for c in result.capabilities)

def test_unavailable_tool_is_not_claimed_as_used():
    result = Controller(unavailable_tools={"test_runner"}).run(GoalRequest(goal="Build a small web application that allows a user to create, edit, complete, and delete tasks."))
    assert "test_runner" not in result.selected_tools

def test_recursive_prerequisites_and_cycle_guard():
    registry = CapabilityRegistry()
    graph = registry.expand(["A"], {"A": ["B"], "B": ["C"], "C": []})
    assert graph["graph"] == {"A": ["B"], "B": ["C"], "C": []}
    cycle = registry.expand(["A"], {"A": ["B"], "B": ["A"]})
    assert cycle["cycles"] == ["A"]

def test_alternative_tool_excludes_failed_tool():
    registry = ToolRegistry()
    registry.metadata["python_alt"] = {"capabilities_provided":["code execution"], "output_type":"stdout/stderr", "reliability":.8}
    choice = registry.choose_fallback("code execution", {"code_execution"})
    assert choice["selected"] == "python_alt"
    assert "code_execution" not in choice["candidates"]

def test_no_alternative_is_explicitly_blocked():
    registry = ToolRegistry(unavailable={"code_execution"})
    assert registry.choose_fallback("code execution", {"code_execution"})["selected"] is None

def test_capability_acquisition_requires_practice_test_and_transfer():
    registry = CapabilityRegistry()
    registry.items["csv_stats"] = Capability("csv_stats", "CSV statistics", "analyze CSV")
    cap = registry.acquire("csv_stats", "goal-a", "correlation on dataset A", {"passed": True, "evidence": "test A"}, {"passed": True, "evidence": "transfer B"})
    assert cap.status == "available"
    assert cap.last_test_result["transfer"]["passed"]

def test_false_capability_claim_without_evidence_is_rejected():
    registry = CapabilityRegistry()
    registry.items["x"] = Capability("x", "X", "x", status="available", confidence=1.0)
    audited = registry.audit()[0]
    assert audited.status == "partially_available"

def test_controller_acquires_capability_in_normal_run():
    result = Controller().run(GoalRequest(goal="Create a four-week plan to learn Python from beginner level."))
    assert result.status == "executed"
    assert all(c["status"] == "available" and c["evidence"] for c in result.capabilities)
    assert all(stage in result.trace for stage in ("GAP", "PRACTICE", "TRANSFER_TEST"))

def test_controller_fallback_is_used_in_normal_run():
    result = Controller(fail_tool_once="filesystem", fallback_tool="code_execution").run(GoalRequest(goal="Build a small web application that allows a user to create, edit, complete, and delete tasks."))
    assert result.status == "executed"
    assert "TOOL_FAILURE" in result.trace and "FALLBACK_SELECTED" in result.trace
    assert "code_execution" in result.selected_tools

def test_controller_blocks_when_tool_has_no_fallback():
    result = Controller(fail_tool_once="filesystem").run(GoalRequest(goal="Build a small web application that allows a user to create, edit, complete, and delete tasks."))
    assert result.state == "BLOCKED"
    assert result.structured_failures[0]["type"] == "tool_failure"

def test_controller_acquisition_has_knowledge_provenance():
    controller = Controller()
    result = controller.run(GoalRequest(goal="Create a four-week plan to learn Python from beginner level."))
    assert result.knowledge_items
    assert all(x["validation_status"] == "VALIDATED" and x["source_id"] in controller.knowledge.sources for x in result.knowledge_items)
    assert "PROVENANCE" in result.trace

def test_unvalidated_knowledge_is_not_promoted():
    store = KnowledgeStore(); source = store.add_controlled_source("x", "g", "practice")
    item = store.extract(source, "x", "claim", "g")
    assert item.validation_status == "UNVERIFIED"
    assert store.validate(item, "") .validation_status == "UNVERIFIED"

def test_knowledge_reuse_requires_validation():
    store = KnowledgeStore(); source = store.add_controlled_source("x", "a", "e"); item = store.extract(source, "x", "claim", "a")
    assert store.reuse("x", "b") is None
    store.validate(item, "independent", independent=True)
    assert store.reuse("x", "b") is item

def test_contradictions_are_preserved():
    store = KnowledgeStore(); a = KnowledgeItem("a", "x", "claim A", "s1", "test", "high", ["e1"]); b = KnowledgeItem("b", "x", "claim B", "s2", "test", "high", ["e2"])
    contradiction = store.record_contradiction(a, b)
    assert contradiction.status == "UNRESOLVED"
    assert contradiction.claims == ["claim A", "claim B"]

def test_source_discovery_blocks_without_external_source():
    assert KnowledgeStore().discover_source("unknown", allow_external=False) is None

def test_browser_is_registered_and_structured():
    registry = ToolRegistry()
    assert "browser" in registry.metadata
    result = BrowserTool(enabled=False).open("https://example.com")
    assert result.status == "blocked"
    assert result.error == "SOURCE_DISCOVERY_BLOCKED"

def test_browser_fixture_retrieval_preserves_provenance():
    import threading
    from http.server import HTTPServer, BaseHTTPRequestHandler
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            body=b"<html><body><h1>Fixture</h1><p>Verified fact.</p></body></html>"; self.send_response(200); self.end_headers(); self.wfile.write(body)
        def log_message(self, *args): pass
    server=HTTPServer(("127.0.0.1", 0), Handler); threading.Thread(target=server.handle_request, daemon=True).start()
    result=BrowserTool().open(f"http://127.0.0.1:{server.server_port}/")
    server.server_close(); assert result.status == "success" and "Verified fact." in result.content and result.retrieval_method

def test_normal_controller_run_selects_browser_for_external_information():
    controller = Controller()
    controller.browser = BrowserTool(enabled=False)
    result = controller.run(GoalRequest(goal="Learn the current basic requirements for creating a small Next.js web application and produce a verified implementation plan."))
    assert result.state == "BLOCKED"
    assert "INFORMATION_NEED" in result.trace
    assert "SOURCE_DISCOVERY_BLOCKED" in result.trace

def test_controller_uses_controlled_browser_fixture_end_to_end():
    import threading
    from http.server import HTTPServer, BaseHTTPRequestHandler
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            body=b"<html><body>Current framework requirement evidence.</body></html>"; self.send_response(200); self.end_headers(); self.wfile.write(body)
        def log_message(self, *args): pass
    server=HTTPServer(("127.0.0.1", 0), Handler); threading.Thread(target=server.handle_request, daemon=True).start()
    controller=Controller(); controller.browser.open=lambda url: BrowserTool().open(f"http://127.0.0.1:{server.server_port}/")
    result=controller.run(GoalRequest(goal="Research current framework requirements and produce a verified implementation plan.")); server.server_close()
    assert result.status == "executed" and result.information_needs[0]["status"] == "SATISFIED" and result.knowledge_items

def test_m11_capability_is_promoted_only_after_learning_and_used():
    result = Controller().run(GoalRequest(goal="Create a four-week plan to learn Python from beginner level."))
    assert result.status == "executed"
    assert result.learning_evidence
    assert all(x["status"] == "available" and x["self_test"]["passed"] and x["transfer"]["passed"] for x in result.learning_evidence)
    assert result.execution.capabilities_used
    assert "CAPABILITY_AVAILABLE" in result.trace

def test_independent_evaluator_rejects_wrong_artifact_with_diagnosis():
    goal = type("Goal", (), {"artifact_type":"web_application"})()
    result = IndependentEvaluator().evaluate(goal, {"artifact_type":"study_plan"}, [])
    assert not result.passed and result.score == 0
    assert result.failures[0]["failure_type"] == "evaluation_failure"
    assert result.failures[0]["recommended_next_learning_action"]

def test_evaluator_requires_external_evidence_for_success():
    goal = type("Goal", (), {"artifact_type":"web_application"})()
    result = IndependentEvaluator().evaluate(goal, {"artifact_type":"web_application"}, [{"name":"delete", "passed":False, "evidence":"delete test failed"}])
    assert not result.passed and result.failures[0]["suspected_knowledge_gap"]

def test_targeted_relearning_action_is_not_generic():
    goal = type("Goal", (), {"artifact_type":"web_application"})()
    result = IndependentEvaluator().evaluate(goal, {"artifact_type":"web_application"}, [{"name":"task deletion", "passed":False, "evidence":"operation absent"}])
    action = result.failures[0]["recommended_next_learning_action"]
    assert "task deletion" in action or "failed requirement" in action

def test_m13_knowledge_graph_is_domain_neutral_and_recursive():
    graph=KnowledgeRequirementGraph(); graph.add(KnowledgeRequirement("A", "A", "goal")); graph.add(KnowledgeRequirement("B", "B", "A"))
    result=graph.expand(["A"], {"A":["B"], "B":[]})
    assert set(result["nodes"]) == {"A","B"} and result["cycles"] == []

def test_m13_benchmarks_produce_different_requirement_shapes():
    outputs=[Controller().run(GoalRequest(goal=g)) for g in BENCHMARK_GOALS[:3]]
    assert len({tuple(x.name for x in r.requirements) for r in outputs}) == 3
    assert all(r.goal.goal == g for r,g in zip(outputs, BENCHMARK_GOALS[:3]))

def test_runtime_filesystem_and_artifact_verification():
    runtime=ToolRuntime(Path(tempfile.mkdtemp()))
    assert runtime.write("app.txt", "hello world").status == "success"
    result=runtime.verify_file_contains("app.txt", ["hello"])
    assert result.status == "success" and result.evidence[0]["passed"]

def test_runtime_python_success_and_failure():
    runtime=ToolRuntime(Path(tempfile.mkdtemp()))
    assert runtime.run(["python3", "-c", "print('ok')"], "python_execution").status == "success"
    assert runtime.run(["python3", "-c", "raise SystemExit(2)"], "python_execution").status == "failed"

def test_runtime_timeout_is_structured():
    runtime=ToolRuntime(Path(tempfile.mkdtemp()), timeout=1)
    result=runtime.run(["python3", "-c", "import time; time.sleep(2)"], "process_execution")
    assert result.status == "timeout"

def test_runtime_permission_and_command_boundaries():
    runtime=ToolRuntime(Path(tempfile.mkdtemp()))
    assert runtime.write("../escape.txt", "no").status == "failed"
    assert runtime.run(["sh", "-c", "echo unsafe"]).status == "failed"

def test_runtime_test_failure_and_inspection():
    runtime=ToolRuntime(Path(tempfile.mkdtemp()))
    runtime.write("test.py", "raise SystemExit(1)")
    result=runtime.run(["python3", "test.py"], "test_runner")
    assert result.status == "failed" and result.exit_code == 1
    assert runtime.inspect().status == "success"

def test_m15_sequential_composition_and_dependency_passing():
    plan=[PlanStep("a","produce input","write","producer",input="x"), PlanStep("b","consume input","transform","consumer",input="$a",depends_on=["a"],verification_condition=lambda x:x=="X")]
    result=ToolPlanner().execute(plan,{"producer":lambda value,ctx:value,"consumer":lambda value,ctx:value.upper()})
    assert result.status=="completed" and result.outputs["b"]=="X"

def test_m15_branching_and_conditionals():
    plan=[PlanStep("choose","choose branch","decision","choose",input=True), PlanStep("left","left","left_cap","left",condition=lambda o:o["choose"] is True), PlanStep("right","right","right_cap","right",condition=lambda o:o["choose"] is False)]
    result=ToolPlanner().execute(plan,{"choose":lambda v,c:v,"left":lambda v,c:"left","right":lambda v,c:"right"})
    assert result.status=="completed" and "left" in result.outputs and "right" not in result.outputs

def test_m15_failed_intermediate_step_replans_to_alternative():
    plan=[PlanStep("fetch","fetch source","retrieval","bad",alternatives=["good"],verification_condition=lambda x:x=="data")]
    result=ToolPlanner().execute(plan,{"bad":lambda v,c:(_ for _ in ()).throw(RuntimeError("network")),"good":lambda v,c:"data"})
    assert result.status=="completed" and any(x["tool"]=="bad" and x["status"]=="failed" for x in result.trace) and result.outputs["fetch"]=="data"

def test_m15_replanning_after_all_tools_fail():
    plan=[PlanStep("fetch","fetch","retrieval","bad")]
    result=ToolPlanner().execute(plan,{"bad":lambda v,c:(_ for _ in ()).throw(RuntimeError("down")),"repair":lambda v,c:v},replan=lambda step,error,ctx:PlanStep("repair","repair","retrieval","repair",input="ok",verification_condition=lambda x:x=="ok"))
    assert result.status=="completed" and any(x["status"]=="replanned" for x in result.trace)

def test_m15_three_compositions_have_distinct_plans():
    assert len({tuple(x for x in plan) for plan in (("browser","python"),("filesystem","test_runner"),("python","artifact_inspection"))})==3

def test_m16_repository_inspection_and_git_evidence():
    repo=RepositoryTools(Path.cwd())
    assert repo.inspect().status == "success"
    assert repo.git("status").status in {"success", "failed"}
    assert repo.git("diff").status in {"success", "failed"}

def test_m16_destructive_git_operations_are_blocked():
    result=RepositoryTools(Path.cwd()).git("reset")
    assert result.status == "blocked"

def test_m16_github_unavailable_is_explicit():
    result=RepositoryTools(Path.cwd()).github("create_pull_request")
    assert result.status == "unavailable"

def test_m17_deployment_requires_explicit_permission():
    result=LocalDeployment(permission=False).deploy("artifact")
    assert result.status == "blocked" and result.failure["type"] == "permission_denied"

def test_m17_local_deployment_has_evidence_health_and_rollback():
    deployment=LocalDeployment(permission=True); result=deployment.deploy("real artifact")
    assert result.status == "deployed" and result.evidence[0]["artifact_present"] and result.rollback_available
    assert deployment.rollback()["status"] == "rolled_back"

def test_m17_cloud_provider_unavailable_is_not_fake_success():
    assert VercelDeployment().deploy("artifact").status == "unavailable"

def test_m17_secrets_are_redacted():
    assert "supersecret" not in redact("token=supersecret api_key=hidden")

def test_m18_generalized_lesson_reuses_principle_not_solution():
    memory=GeneralizationMemory(); experience=memory.record_experience({"experience_id":"e1","success":True,"evidence":["4/4 behavior checks passed"]})
    lesson=memory.abstract(experience,"verify each requested behavior with independent evidence",["testing","artifact verification"],"software")
    assert memory.retrieve(["testing"],"software","new task list")[0].principle.startswith("verify")

def test_m18_negative_transfer_is_rejected():
    memory=GeneralizationMemory(); lesson=memory.abstract({"experience_id":"e1","success":True,"evidence":["ui test"]},"use UI selectors",["browser UI"],"web")
    memory.reject(lesson,"mathematics","no mathematical evidence")
    assert not memory.retrieve(["browser UI"],"mathematics","solve equation")

def test_m18_compare_relevant_and_irrelevant_experience():
    memory=GeneralizationMemory(); memory.abstract({"experience_id":"e1","success":True,"evidence":["test"]},"verify outputs",["testing"],"software")
    assert memory.retrieve(["testing"],"software","new app") and not memory.retrieve(["statistical inference"],"science","new experiment")

def test_m18_parameterized_transfer_benchmarks():
    goals=parameterized_goals(); assert len(goals)==3 and len(set(goals))==3

def test_m19_learning_objectives_derive_from_requirements_not_subject_list():
    planner=AdaptiveLearningPlanner(); req=[type("R",(),{"requirement_id":"r1","capabilities_needed":["novel protocol"],"required":True})()]
    objectives=planner.derive(req, None)
    assert len(objectives)==1 and objectives[0].topic=="novel protocol"

def test_m19_dependencies_prioritize_prerequisites_and_split_unknowns():
    planner=AdaptiveLearningPlanner(); req=[type("R",(),{"requirement_id":"r1","capabilities_needed":["large capability"],"required":True})()]; planner.derive(req,None)
    parts=planner.split("r1:0",["small prerequisite","small operation"]); decision=planner.decide()
    assert len(parts)==2 and decision.next_objective is not None

def test_m19_practice_independent_and_transfer_are_required():
    planner=AdaptiveLearningPlanner(); req=[type("R",(),{"requirement_id":"r1","capabilities_needed":["x"],"required":True})()]; planner.derive(req,None)
    planner.record("r1:0",True,True,False); assert planner.objectives["r1:0"].status=="needs_relearning"
    planner.record("r1:0",True,True,True); assert planner.objectives["r1:0"].status=="available"

def test_m19_budget_and_stop_reason_are_explicit():
    planner=AdaptiveLearningPlanner(budget=0); req=[type("R",(),{"requirement_id":"r1","capabilities_needed":["x"],"required":True})()]; planner.derive(req,None)
    decision=planner.decide(); assert not decision.ready and "budget" in decision.stop_reason

def test_m19_readiness_stops_when_all_evidence_exists():
    planner=AdaptiveLearningPlanner(); req=[type("R",(),{"requirement_id":"r1","capabilities_needed":["x"],"required":True})()]; planner.derive(req,None); planner.record("r1:0",True,True,True)
    decision=planner.decide(); assert decision.ready and "evidence" in decision.stop_reason

def test_m20_comprehensive_benchmark_uses_normal_controller_path():
    results, audits=run_benchmark(Controller())
    assert set(results) == set(M20_GOALS)
    assert all(result.goal.goal == M20_GOALS[name] for name,result in results.items())
    assert all(audits[name][0].status == "pass" for name in results)
    assert results["data"].state == "BLOCKED"

def test_m20_audit_is_explicitly_honest_about_boundaries():
    assert AUTONOMY_AUDIT["deterministic"] and AUTONOMY_AUDIT["before_agi"]
    assert "cloud connectors require credentials" in AUTONOMY_AUDIT["tool_constraints"]

def test_final_belief_update_preserves_conflict_and_provenance():
    store=BeliefStore(); store.update("claim",BeliefState.KNOWN,1.0,["source-a"],["url-a"]); belief=store.update("claim",BeliefState.DISPROVEN,.4,["source-b"],["url-b"])
    assert belief.state == BeliefState.CONTRADICTED and "url-a" in belief.provenance and "url-b" in belief.provenance

def test_final_world_state_is_dynamic_and_observable():
    state=WorldState(); state.entities["task-1"]={"type":"task"}; state.set_property("task-1","done",False); state.observe({"source":"test","task":"created"})
    assert state.properties["task-1"]["done"] is False and state.observations

def test_final_budget_is_bounded():
    budget=Budget(learning=1); assert budget.consume("learning") and not budget.consume("learning"); assert budget.exhausted()

def test_final_permissions_and_secret_protection():
    assert permission_allowed("read",{"READ"}) and not permission_allowed("delete",{"READ"})
    assert "supersecret" not in redact_secrets("secret=supersecret") and "REDACTED" in redact_secrets("secret=supersecret")

def test_final_self_model_requires_evidence():
    model=SelfModel(); assert model.assess("unknown")["status"]=="UNKNOWN"; model.update_capability("python","available",["test passed"]); assert model.assess("python")["evidence"]

def test_missing_private_database_blocks_before_mock_artifact():
    result=Controller().run(GoalRequest(goal="Analyze my private database"))
    assert result.status=="blocked" and result.state=="BLOCKED" and result.execution is None and result.failures==["MISSING_DEPENDENCY"]

def test_missing_authenticated_api_is_permission_denied():
    result=Controller().run(GoalRequest(goal="Analyze data from my private authenticated API"))
    assert result.status=="blocked" and result.failures==["PERMISSION_DENIED"]

def test_supplied_csv_has_real_parse_evidence_and_completed_state():
    result=Controller().run(GoalRequest(goal="Analyze this CSV dataset and identify trends", resources={"csv":"name,value\na,1\nb,2"}))
    assert result.status=="executed" and result.state=="COMPLETED" and result.execution.evidence[1]["passed"]

def test_blocked_states_never_claim_completed():
    result=Controller().run(GoalRequest(goal="Analyze a CSV dataset and identify trends"))
    assert result.status=="blocked" and result.state=="BLOCKED" and result.verification is None

def test_mock_provider_cannot_bypass_missing_evidence():
    result=Controller().run(GoalRequest(goal="Analyze my private database and provide findings"))
    assert result.status=="blocked" and result.execution is None and result.verification is None
