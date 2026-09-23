from __future__ import annotations
from dataclasses import dataclass, field

@dataclass
class GeneralizedLesson:
    lesson_id: str; principle: str; source_experience: str; applicable_capabilities: list[str]; domain: str; confidence: float; evidence: list[str] = field(default_factory=list); rejected_contexts: list[str] = field(default_factory=list)

class GeneralizationMemory:
    def __init__(self): self.experiences=[]; self.lessons=[]
    def record_experience(self, experience: dict): self.experiences.append(experience); return experience
    def abstract(self, experience: dict, principle: str, capabilities: list[str], domain: str):
        lesson=GeneralizedLesson(f"lesson-{len(self.lessons)+1}", principle, experience.get("experience_id", "unknown"), capabilities, domain, 1.0 if experience.get("success") else .5, experience.get("evidence", []) or [experience.get("outcome", "")]); self.lessons.append(lesson); return lesson
    def retrieve(self, capabilities: list[str], domain: str, task: str):
        matches=[]
        for lesson in self.lessons:
            overlap=len(set(capabilities)&set(lesson.applicable_capabilities))
            if overlap and domain not in lesson.rejected_contexts: matches.append((overlap + (1 if lesson.domain == domain else 0), lesson))
        return [x[1] for x in sorted(matches, key=lambda x:x[0], reverse=True)]
    def reject(self, lesson: GeneralizedLesson, context: str, evidence: str): lesson.rejected_contexts.append(context); lesson.evidence.append(f"rejected:{evidence}"); return lesson

def parameterized_goals(): return [f"Create a task list with {n} items and verify completion behavior" for n in (2, 5, 9)]
