import logging
from typing import Any, Dict
from pathlib import Path

from services.context_builder_service import ContextBuilderService
from services.planner.planner_agent_service import PlannerAgentService
from services.generator.code_generator_service import CodeGeneratorService

logger = logging.getLogger(__name__)


class MigrationWorkflowService:
    """Lightweight custom workflow coordinator for migration steps."""

    def __init__(
        self, 
        context_builder: ContextBuilderService | None = None, 
        planner_agent: PlannerAgentService | None = None,
        code_generator: CodeGeneratorService | None = None
    ):
        self.context_builder = context_builder or ContextBuilderService()
        self.planner_agent = planner_agent or PlannerAgentService()
        # generator is initialized per request using paths, or stored if passed
        self.code_generator = code_generator

    def run_migrate_infra(self, project_id: str) -> Dict[str, Any]:
        result = self.context_builder.build_planner_context(project_id, workflow_scope="infra")
        logger.info("Final planner prompt for project %s:\n%s", project_id, result["prompt"])
        return result

    def invoke_planner(self, project_id: str) -> Dict[str, Any]:
        logger.info("Building planner context for project %s", project_id)
        # We re-build context here so that planner gets everything needed.
        context_payload = self.context_builder.build_planner_context(project_id, workflow_scope="infra")
        
        logger.info("Executing Planner Agent for project %s. This might take a bit.", project_id)
        result = self.planner_agent.generate_plan(project_id, context_payload)
        
        logger.info("Planner Agent plan generated successfully for project %s", project_id)
        return {
            "project_id": project_id,
            "status": "completed",
            "migration_plan": result["plan"],
            "telemetry": result["telemetry"]
        }

    def invoke_generator(self, project_id: str, plan_payload: Dict[str, Any]) -> Dict[str, Any]:
        """Executes the migration plan payload using the Code Generator Service."""
        logger.info("Resolving paths for Code Generator agent on project %s", project_id)
        context_payload = self.context_builder.build_planner_context(project_id, workflow_scope="infra")
        context = context_payload.get("context", {})
        where = context.get("where", {})
        
        if not where.get("source_repository_path") or not where.get("target_repository_path"):
            raise ValueError("Missing filesystem paths for project migration execution.")

        source_repo_path = Path(where["source_repository_path"])
        target_repo_path = Path(where["target_repository_path"])

        generator = self.code_generator or CodeGeneratorService(
            source_repo_path=source_repo_path, 
            target_repo_path=target_repo_path
        )
        
        logger.info("Starting Code Generation step for project %s", project_id)
        results = generator.generate_code(plan_payload, context_payload)
        
        return {
            "project_id": project_id,
            "status": "completed",
            "generation_results": results
        }
