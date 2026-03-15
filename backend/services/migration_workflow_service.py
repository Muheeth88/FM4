import logging
from typing import Any, Dict

from services.context_builder_service import ContextBuilderService

logger = logging.getLogger(__name__)


class MigrationWorkflowService:
    """Lightweight custom workflow coordinator for migration steps."""

    def __init__(self, context_builder: ContextBuilderService | None = None):
        self.context_builder = context_builder or ContextBuilderService()

    def run_migrate_infra(self, project_id: str) -> Dict[str, Any]:
        result = self.context_builder.build_planner_context(project_id, workflow_scope="infra")
        logger.info("Final planner prompt for project %s:\n%s", project_id, result["prompt"])
        return result
