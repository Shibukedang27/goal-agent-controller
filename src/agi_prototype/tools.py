from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import json, subprocess, tempfile

@dataclass
class Evidence:
    name: str
    expected: str
    actual: str
    passed: bool
    logs: str = ""

class SafeWorkspace:
    def __init__(self, root: Path | None = None):
        self.root = root or Path(tempfile.mkdtemp(prefix="agi-run-"))
        self.root.mkdir(parents=True, exist_ok=True)
    def write(self, relative: str, content: str) -> Path:
        target = (self.root / relative).resolve()
        if self.root.resolve() not in target.parents: raise ValueError("path outside workspace")
        target.parent.mkdir(parents=True, exist_ok=True); target.write_text(content); return target
    def inspect(self): return sorted(str(p.relative_to(self.root)) for p in self.root.rglob("*") if p.is_file())
    def run(self, command: list[str], timeout: int = 5):
        allowed = {"python", "python3"}
        if not command or command[0] not in allowed: raise ValueError("command not allowed")
        return subprocess.run(command, cwd=self.root, capture_output=True, text=True, timeout=timeout)

class ToolRegistry:
    def __init__(self, unavailable: set[str] | None = None):
        self.unavailable = unavailable or set()
        self.metadata = {
            "filesystem": {"capabilities_provided":["file access"], "output_type":"files", "reliability":.99},
            "code_execution": {"capabilities_provided":["code execution"], "output_type":"stdout/stderr", "reliability":.95},
            "test_runner": {"capabilities_provided":["testing"], "output_type":"evidence", "reliability":.95},
            "data_analysis": {"capabilities_provided":["data analysis"], "output_type":"findings", "reliability":.9},
            "artifact_writer": {"capabilities_provided":["artifact generation"], "output_type":"artifact", "reliability":.95},
            "evidence_collector": {"capabilities_provided":["evidence generation"], "output_type":"evidence", "reliability":.95},
            "browser": {"capabilities_provided":["web_search", "web_page_retrieval", "external information acquisition"], "output_type":"source evidence", "reliability":.8},
            "terminal": {"capabilities_provided":["terminal execution"], "output_type":"stdout/stderr", "reliability":.9},
            "process_execution": {"capabilities_provided":["process execution"], "output_type":"exit code", "reliability":.9},
            "python_execution": {"capabilities_provided":["Python execution"], "output_type":"stdout/stderr", "reliability":.95},
            "test_runner": {"capabilities_provided":["test execution"], "output_type":"test evidence", "reliability":.95},
            "artifact_inspection": {"capabilities_provided":["artifact verification"], "output_type":"inspection evidence", "reliability":.98},
            "project_inspection": {"capabilities_provided":["repository inspection"], "output_type":"file inventory", "reliability":.98},
            "git": {"capabilities_provided":["repository state", "diff inspection"], "output_type":"structured repository evidence", "reliability":.98},
            "github": {"capabilities_provided":["remote repository operations"], "output_type":"remote repository result", "reliability":0.0},
            "local_deployment": {"capabilities_provided":["deployment", "health checks", "rollback"], "output_type":"deployment evidence", "reliability":.9},
            "vercel": {"capabilities_provided":["cloud deployment", "deployment logs"], "output_type":"cloud deployment evidence", "reliability":0.0},
        }
    def select(self, artifact_type: str, missing_dependency: bool = False):
        if missing_dependency: return ["dependency_inspector"]
        selected = {"web_application": ["filesystem", "code_execution", "test_runner"], "analysis": ["filesystem", "data_analysis", "evidence_collector"], "study_plan": ["artifact_writer", "evidence_collector"]}.get(artifact_type, ["artifact_writer", "evidence_collector"])
        return [x for x in selected if x not in self.unavailable]
    def candidates(self, capability: str, failed: set[str] | None = None):
        failed = failed or set()
        return [tool_id for tool_id, meta in self.metadata.items() if tool_id not in self.unavailable and tool_id not in failed and any(capability.lower() in x.lower() or x.lower() in capability.lower() for x in meta["capabilities_provided"])]
    def choose_fallback(self, capability: str, failed: set[str]):
        candidates = self.candidates(capability, failed)
        return {"capability": capability, "failed_tools": sorted(failed), "candidates": candidates, "selected": candidates[0] if candidates else None}
