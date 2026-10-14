from fastapi import FastAPI
from .core import Controller
from .models import GoalRequest, RunResult

app = FastAPI(title="Goal Agent Controller", version="0.1.0")
controller = Controller()

@app.get("/")
def root():
    return {
        "name": "Goal Agent Controller",
        "status": "running",
        "docs": "/docs",
        "health": "/health",
        "run_goal": "POST /runs",
    }

@app.get("/health")
def health(): return {"status": "ok", "provider": "local-rule-provider"}

@app.post("/runs", response_model=RunResult)
def run_goal(request: GoalRequest): return controller.run(request)

@app.get("/memory")
def memory(): return {"entries": controller.memory.all()}
