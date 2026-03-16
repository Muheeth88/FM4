import json
import logging
from pathlib import Path
from typing import Any, Dict, List
from datetime import datetime

from langchain_core.tools import StructuredTool
from pydantic import ValidationError

from services.llm.agent_service import BaseLLMAgentService
from models.planner_models import PlannerOutputSchema

logger = logging.getLogger(__name__)


def create_planner_tools(source_repo_path: Path) -> List[StructuredTool]:
    """Create Langchain tools scoped to the specific repository."""

    def _read_file(path: str) -> str:
        """Return the contents of a single file."""
        target = source_repo_path / path
        try:
            if not target.resolve().is_relative_to(source_repo_path.resolve()):
                return f"Error: Path {path} is outside the repository."
            if not target.exists():
                return f"Error: File {path} does not exist."
            if target.is_dir():
                return f"Error: Path {path} is a directory."
            return target.read_text(encoding="utf-8")
        except Exception as e:
            return f"Error reading file {path}: {e}"

    def _read_files(paths: list[str]) -> dict:
        """Return contents of multiple files."""
        result = {}
        for p in paths:
            result[p] = _read_file(p)
        return result

    def _list_directory(path: str) -> list[str]:
        """Return files and folders inside a directory."""
        target = source_repo_path / path
        try:
            if not target.resolve().is_relative_to(source_repo_path.resolve()):
                return ["Error: Path is outside the repository."]
            if not target.exists() or not target.is_dir():
                return [f"Error: Directory {path} does not exist."]
            
            return [p.name for p in target.iterdir()]
        except Exception as e:
            return [f"Error listing directory {path}: {e}"]

    def _search_code(pattern: str) -> list[str]:
        """Search repository for files containing a string pattern."""
        try:
            matches = []
            for filepath in source_repo_path.rglob("*"):
                if filepath.is_file():
                    try:
                        content = filepath.read_text(encoding="utf-8", errors="ignore")
                        if pattern in content:
                            matches.append(str(filepath.relative_to(source_repo_path).as_posix()))
                    except Exception:
                        pass
            return matches
        except Exception as e:
            return [f"Error searching code for pattern '{pattern}': {e}"]

    return [
        StructuredTool.from_function(
            func=_read_file,
            name="read_file",
            description="Return the contents of a single file.",
        ),
        StructuredTool.from_function(
            func=_read_files,
            name="read_files",
            description="Return contents of multiple files.",
        ),
        StructuredTool.from_function(
            func=_list_directory,
            name="list_directory",
            description="Return files and folders inside a directory.",
        ),
        StructuredTool.from_function(
            func=_search_code,
            name="search_code",
            description="Search repository for files containing a string.",
        )
    ]


class PlannerAgentService:
    """Invokes the LLM to generate a deterministic migration execution plan."""

    def __init__(self):
        pass

    def generate_plan(self, project_id: str, context_payload: Dict[str, Any]) -> Dict[str, Any]:
        """Generate a valid migration plan using the Context Builder's payload."""
        context = context_payload.get("context", {})
        source_repo_path_str = context.get("where", {}).get("source_repository_path")
        
        if not source_repo_path_str:
            raise ValueError("source_repository_path is missing from context payload.")

        source_repo_path = Path(source_repo_path_str)
        tools = create_planner_tools(source_repo_path)

        system_prompt = context.get("basic_system_prompt", "")
        # Enforce JSON output explicitly
        system_prompt += (
            "\n\nCRITICAL: You MUST output ONLY raw JSON that strictly conforms to the Planner Output Schema. "
            "Do not include markdown blocks (like ```json), explanations, or any other text. "
            "Your output must be immediately parsable by json.loads()."
        )

        agent = BaseLLMAgentService(
            system_prompt=system_prompt,
            tools=tools,
            model="gpt-4o",
            temperature=0,
            max_retries=2
        )

        prompt_input = json.dumps(context, indent=2)

        logger.info(f"Invoking Planner Agent with Context Builder payload for project {project_id}")
        response = agent.invoke_json_with_metadata(prompt_input)
        raw_output = response["output"]
        telemetry = response["metadata"]

        if isinstance(raw_output, dict):
            raw_output["planner_version"] = "1.0.0"
            raw_output["planner_model"] = agent.model
            raw_output["planning_timestamp"] = datetime.utcnow().isoformat() + "Z"
            # Ensure languages are set if missing
            raw_output.setdefault("source_language", context.get("repository_metadata", {}).get("source_language", "unknown"))
            raw_output.setdefault("target_language", context.get("repository_metadata", {}).get("target_language", "unknown"))

        logger.info("Planner Agent returned a JSON payload. Validating schema...")
        if isinstance(raw_output, dict) and "plan_units" in raw_output:
            for unit in raw_output["plan_units"]:
                if "target_paths_final" in unit and isinstance(unit["target_paths_final"], list):
                    # Deduplicate while preserving order
                    seen = set()
                    deduped = []
                    for path in unit["target_paths_final"]:
                        if path not in seen:
                            seen.add(path)
                            deduped.append(path)
                    unit["target_paths_final"] = deduped

        try:
            validated_plan = PlannerOutputSchema(**raw_output)
            plan_dict = validated_plan.model_dump()
            logger.info("Planner plan validated successfully.")
            return {"plan": plan_dict, "telemetry": telemetry}
        except ValidationError as e:
            logger.error("Planner output failed to validate against output schema.")
            raise ValueError(f"Planner plan validation failed: {str(e)}")
