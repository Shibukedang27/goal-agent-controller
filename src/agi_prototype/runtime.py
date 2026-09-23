from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
import subprocess, sys, time

@dataclass
class ToolResult:
    tool_id: str; operation: str; status: str; exit_code: int | None = None
    stdout: str = ""; stderr: str = ""; evidence: list[dict] = field(default_factory=list)
    error: str | None = None; duration_ms: int = 0; files: list[str] = field(default_factory=list)

class ToolRuntime:
    def __init__(self, workspace: Path, timeout: int = 5, allowed_tools: set[str] | None = None):
        self.workspace = workspace.resolve(); self.workspace.mkdir(parents=True, exist_ok=True); self.timeout=timeout; self.allowed_tools=allowed_tools or {"filesystem","terminal","process_execution","python_execution","test_runner","artifact_inspection"}
    def _check(self, tool: str):
        if tool not in self.allowed_tools: raise PermissionError(f"tool_not_allowed:{tool}")
    def _path(self, relative: str):
        target=(self.workspace/relative).resolve()
        if self.workspace not in target.parents and target != self.workspace: raise PermissionError("path_outside_workspace")
        return target
    def write(self, relative: str, content: str):
        try:
            self._check("filesystem"); path=self._path(relative); path.parent.mkdir(parents=True, exist_ok=True); path.write_text(content)
            return ToolResult("filesystem","write","success",files=[relative],evidence=[{"file":relative,"exists":path.exists()}])
        except (PermissionError, OSError) as exc: return ToolResult("filesystem","write","failed",error=str(exc))
    def inspect(self, relative: str = "."):
        try:
            self._check("artifact_inspection"); path=self._path(relative); files=[str(x.relative_to(self.workspace)) for x in path.rglob("*") if x.is_file()] if path.is_dir() else [relative]
            return ToolResult("artifact_inspection","inspect","success",files=files,evidence=[{"file":x,"exists":True} for x in files])
        except (PermissionError, OSError) as exc: return ToolResult("artifact_inspection","inspect","failed",error=str(exc))
    def run(self, command: list[str], tool_id: str = "terminal"):
        try:
            self._check(tool_id)
            if not command or command[0] not in {"python", "python3", sys.executable}: return ToolResult(tool_id,"run","failed",error="command_not_allowed")
            start=time.monotonic(); proc=subprocess.run(command,cwd=self.workspace,capture_output=True,text=True,timeout=self.timeout); duration=int((time.monotonic()-start)*1000)
            status="success" if proc.returncode == 0 else "failed"
            return ToolResult(tool_id,"run",status,proc.returncode,proc.stdout,proc.stderr,[],None,duration)
        except subprocess.TimeoutExpired as exc: return ToolResult(tool_id,"run","timeout",error="timeout",stdout=exc.stdout or "",stderr=exc.stderr or "")
        except (PermissionError, OSError) as exc: return ToolResult(tool_id,"run","failed",error=str(exc))
    def verify_file_contains(self, relative: str, required: list[str]):
        try:
            self._check("artifact_inspection"); content=self._path(relative).read_text(); checks=[{"requirement":x,"passed":x in content} for x in required]; return ToolResult("artifact_inspection","verify","success" if all(x["passed"] for x in checks) else "failed",evidence=checks,files=[relative])
        except (PermissionError, OSError) as exc: return ToolResult("artifact_inspection","verify","failed",error=str(exc))
