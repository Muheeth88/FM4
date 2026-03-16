import logging
from typing import Any, Dict

from services.context_builder_service import ContextBuilderService
from services.planner.planner_agent_service import PlannerAgentService

logger = logging.getLogger(__name__)


class MigrationWorkflowService:
    """Lightweight custom workflow coordinator for migration steps."""

    def __init__(self, context_builder: ContextBuilderService | None = None, planner_agent: PlannerAgentService | None = None):
        self.context_builder = context_builder or ContextBuilderService()
        self.planner_agent = planner_agent or PlannerAgentService()

    def run_migrate_infra(self, project_id: str) -> Dict[str, Any]:
        result = self.context_builder.build_planner_context(project_id, workflow_scope="infra")
        logger.info("Final planner prompt for project %s:\n%s", project_id, result["prompt"])
        return result

    def invoke_planner(self, project_id: str) -> Dict[str, Any]:
        logger.info("Building planner context for project %s", project_id)
        # We re-build context here so that planner gets everything needed.
        context_payload = self.context_builder.build_planner_context(project_id, workflow_scope="infra")
        
        logger.info("Executing Planner Agent for project %s. This might take a bit.", project_id)
        plan = self.planner_agent.generate_plan(project_id, context_payload)
        
        logger.info("Planner Agent plan generated successfully for project %s", project_id)
        return {
            "project_id": project_id,
            "status": "completed",
            "migration_plan": plan
        }
