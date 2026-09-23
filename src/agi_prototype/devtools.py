from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
import subprocess

@dataclass
class DevToolResult:
    tool_id: str; operation: str; status: str; stdout: str = ""; stderr: str = ""; evidence: list[dict] = field(default_factory=list); error: str | None = None

class RepositoryTools:
    """Read-only-by-default repository tooling. No reset, checkout, push, or delete operations."""
    SAFE = {"status", "diff", "log", "show", "list_files"}
    def __init__(self, root: Path): self.root = root.resolve()
    def inspect(self):
        files=[str(p.relative_to(self.root)) for p in self.root.rglob("*") if p.is_file() and ".git" not in p.parts]
        return DevToolResult("project_inspection","list_files","success",evidence=[{"file":x} for x in files])
    def git(self, operation: str):
        if operation not in self.SAFE: return DevToolResult("git",operation,"blocked",error="operation_not_authorized")
        args={"status":["status","--short"],"diff":["diff","--"],"log":["log","-5","--oneline"],"show":["show","--stat"]}[operation]
        try:
            result=subprocess.run(["git",*args],cwd=self.root,capture_output=True,text=True,timeout=5)
            return DevToolResult("git",operation,"success" if result.returncode==0 else "failed",result.stdout,result.stderr,[{"exit_code":result.returncode}])
        except (OSError, subprocess.TimeoutExpired) as exc: return DevToolResult("git",operation,"failed",error=str(exc))
    def github(self, operation: str): return DevToolResult("github",operation,"unavailable",error="no authenticated GitHub connector configured")
