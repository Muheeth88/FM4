from pydantic import BaseModel
from typing import List, Literal, Optional

class PlanSummary(BaseModel):
    total_units: int = 0
    merges: int = 0
    splits: int = 0
    direct_migrations: int = 0

class PlanUnit(BaseModel):
    plan_unit_id: str
    source_migration_unit_ids: List[int]
    source_paths: List[str]
    role: str
    target_role: str
    decision: Literal["migrate", "copy", "analyze_only", "split", "merge", "skip"]
    target_paths_final: List[str]
    depends_on: List[str]
    reason: str
    notes: List[str]

class PlannerOutputSchema(BaseModel):
    planner_version: str
    planner_model: str
    planning_timestamp: str
    source_language: str
    target_language: str
    migration_phase: str
    planning_mode: str
    plan_summary: PlanSummary
    execution_order: List[str]
    plan_units: List[PlanUnit]
    assumptions: List[str]
    risks: List[str]
