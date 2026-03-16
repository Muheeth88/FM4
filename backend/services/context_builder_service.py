import json
import logging
from pathlib import Path
from typing import Any, Dict, List

from database.analyzer_db import AnalyzerDBWrapper
from services.project_service import ProjectService
from services.ruleset_engine import RulesetEngine
from services.source_analyzer.signature_builder import SourceSignatureBuilder

logger = logging.getLogger(__name__)

WORKSPACE_BASE = Path(__file__).parent.parent / "workspace"


class ContextBuilderService:
    """Assemble planner-ready migration context from analyzed repository data."""

    def __init__(
        self,
        ruleset_engine: RulesetEngine | None = None,
        analyzer_db: AnalyzerDBWrapper | None = None,
        signature_builder: SourceSignatureBuilder | None = None,
    ):
        self.ruleset_engine = ruleset_engine or RulesetEngine()
        self.analyzer_db = analyzer_db or AnalyzerDBWrapper()
        self.signature_builder = signature_builder or SourceSignatureBuilder()

    def build_planner_context(self, project_id: str, workflow_scope: str = "infra") -> Dict[str, Any]:
        project = ProjectService.get_project(project_id)
        if not project:
            raise ValueError(f"Project not found: {project_id}")

        source_repo_path = WORKSPACE_BASE / project_id / "source"
        target_repo_path = WORKSPACE_BASE / project_id / "target"

        if not source_repo_path.exists():
            raise FileNotFoundError(f"Source repository not found: {source_repo_path}")
        if not target_repo_path.exists():
            raise FileNotFoundError(f"Target repository not found: {target_repo_path}")

        selected_file_type = "infra_file" if workflow_scope == "infra" else None
        migration_units = self.analyzer_db.get_migration_units(project_id, file_type=selected_file_type)
        if not migration_units:
            raise ValueError(
                f"No migration units found for project {project_id}. "
                "Run repository analysis before context preparation."
            )

        signatures = self.signature_builder.build_signatures([unit["source_path"] for unit in migration_units])
        dependency_edges = self.analyzer_db.get_dependencies(project_id)
        all_files = self.analyzer_db.get_files(project_id)
        stored_summary = self.analyzer_db.get_repository_summary(project_id) or {}
        migration_graph = self._build_migration_graph(
            migration_units,
            dependency_edges,
        )
        migration_units_payload = self._build_migration_units_payload(
            migration_units,
            signatures,
            migration_graph["depends_on_map"],
            source_repo_path,
        )
        repository_summary = self._build_repository_summary(
            all_files,
            stored_summary,
            source_repo_path,
        )
        planner_constraints = self._build_planner_constraints()
        planner_output_schema = self._build_planner_output_schema(workflow_scope)
        repository_structure = self._build_repository_structure(source_repo_path)
        normalized_target_naming_conventions = self._build_target_naming_conventions()

        context = {
            "aim": (
                "Prepare a complete planner handoff for a one-shot infrastructure migration pass so the planner can "
                "plan the migration of the whole repository infrastructure surface in one go."
            ),
            "migration_phase": workflow_scope,
            "target": (
                f"Migrate supporting infrastructure and every non-test asset from "
                f"{project['source']['framework']} {project['source']['language']} "
                f"to {project['target']['framework']} {project['target']['language']} "
                f"inside {target_repo_path}."
            ),
            "why": (
                "The planner needs the repository configuration, transformation rules, repository-wide composition, "
                "and file-by-file structural signatures to make reliable ordering and migration-unit decisions "
                "without re-scanning the repo."
            ),
            "what": (
                f"Process {len(migration_units_payload)} analyzed {workflow_scope} migration units in a single planning step. "
                "This phase covers everything except actual test files."
            ),
            "how": [
                "Use repository metadata to understand the source and target stacks.",
                "Honor the loaded ruleset for classification, naming, target structure, path resolution, and transformations.",
                "Each file is initially treated as a migration unit, but the planner may change this by splitting or merging units.",
                "Consume the precomputed migration_graph topological order from the analyzer rather than recomputing ordering.",
                "Use target_role, target_folder, and target_file_template together with ast_signature and dependencies to decide safe grouping and merge boundaries.",
                "suggestedAction and suggestedTargetPath are preliminary analyzer suggestions. You may override them if dependency structure or target framework architecture requires it.",
                "Plan the whole infra migration in one shot and exclude actual test files from this phase.",
            ],
            "where": {
                "project_id": project_id,
                "workflow_scope": workflow_scope,
                "source_repository_path": str(source_repo_path),
                "target_repository_path": str(target_repo_path),
                "ruleset_id": self.ruleset_engine.ruleset.get("id", self.ruleset_engine.ruleset_name),
            },
            "basic_system_prompt": self._build_system_prompt(workflow_scope),
            "planner_constraints": planner_constraints,
            "planner_output_schema": planner_output_schema,
            "repository_metadata": {
                "target_framework": project["target"]["framework"],
                "source_framework": project["source"]["framework"],
                "source_language": project["source"]["language"],
                "target_language": project["target"]["language"],
                "source_test_engine": project["source"]["test_engine"],
                "target_test_engine": project["target"]["test_engine"],
                "source_branch": project["source"]["branch"],
                "repository_url": project["repo_url"],
            },
            "target_framework_characteristics": {
                "fixture_based": True,
                "async_required": True,
            },
            "repository_summary": repository_summary,
            # "repository_structure": repository_structure,
            "ruleset": {
                "classification": self.ruleset_engine.ruleset.get("classification", {}),
                "target_structure": self.ruleset_engine.ruleset.get("target_structure", {}),
                "naming": self.ruleset_engine.ruleset.get("naming", {})
            },
            "target_naming_conventions": normalized_target_naming_conventions,
            "migration_graph": migration_graph["graph"],
            "migration_units": migration_units_payload,
        }

        prompt = self._build_prompt(context)
        return {
            "project_id": project_id,
            "workflow": f"migrate_{workflow_scope}",
            "status": "completed",
            "prompt": prompt,
            "context": context,
        }

    def _build_migration_units_payload(
        self,
        migration_units: List[Dict[str, Any]],
        signatures: Dict[str, Dict[str, Any]],
        depends_on_map: Dict[int, List[int]],
        source_repo_path: Path,
    ) -> List[Dict[str, Any]]:
        items = []
        for unit in migration_units:
            source_path = Path(unit["source_path"])
            try:
                relative_path = source_path.relative_to(source_repo_path).as_posix()
            except ValueError:
                relative_path = source_path.as_posix()

            normalized_role = self._normalize_file_role(relative_path, unit["actual_role"])
            normalized_suggestion = self._normalize_suggested_migration(
                relative_path,
                unit["suggested_action"],
                unit["suggested_target_path"],
            )
            target_metadata = self._build_target_metadata(
                relative_path,
                normalized_role,
                normalized_suggestion["suggested_target_path"],
            )

            items.append(
                {
                    "migration_unit_id": unit["id"],
                    "source_path": relative_path,
                    "file_name": source_path.name,
                    "role": normalized_role,
                    "file_type": unit["file_type"],
                    "target_role": target_metadata["target_role"],
                    "target_folder": target_metadata["target_folder"],
                    # "target_file_template": target_metadata["target_file_template"],
                    "suggested_action": normalized_suggestion["suggested_action"],
                    "suggested_target_path": normalized_suggestion["suggested_target_path"],
                    "depends_on": depends_on_map.get(unit["id"], []),
                    # "ast_signature": signatures.get(unit["source_path"], {}),
                }
            )

        return items

    def _build_prompt(self, context: Dict[str, Any]) -> str:
        return (
            "Planner Handoff: Context Preparation Output\n\n"
            f"Aim:\n{context['aim']}\n\n"
            f"Migration Phase:\n{context['migration_phase']}\n\n"
            f"Target:\n{context['target']}\n\n"
            f"Why:\n{context['why']}\n\n"
            f"What:\n{context['what']}\n\n"
            "How:\n"
            f"{json.dumps(context['how'], indent=2)}\n\n"
            "Where:\n"
            f"{json.dumps(context['where'], indent=2)}\n\n"
            "Basic System Prompt:\n"
            f"{context['basic_system_prompt']}\n\n"
            "Planner Constraints:\n"
            f"{json.dumps(context['planner_constraints'], indent=2)}\n\n"
            "Planner Output Schema:\n"
            f"{json.dumps(context['planner_output_schema'], indent=2)}\n\n"
            "Repository Metadata:\n"
            f"{json.dumps(context['repository_metadata'], indent=2)}\n\n"
            "Repository Summary:\n"
            f"{json.dumps(context['repository_summary'], indent=2)}\n\n"
            "Target Framework Characteristics:\n"
            f"{json.dumps(context.get('target_framework_characteristics', {}), indent=2)}\n\n"
            "Ruleset:\n"
            f"{json.dumps(context['ruleset'], indent=2)}\n\n"
            "Target Naming Conventions:\n"
            f"{json.dumps(context['target_naming_conventions'], indent=2)}\n\n"
            "Migration Graph:\n"
            f"{json.dumps(context['migration_graph'], indent=2)}\n\n"
            "Migration Units:\n"
            f"{json.dumps(context['migration_units'], indent=2)}\n"
        )

    @staticmethod
    def _build_system_prompt(workflow_scope: str) -> str:
        return (
            "You are the planner agent for the Quality Engineering Framework migration workflow. "
            f"This is a one-shot {workflow_scope} migration planning step. Plan the migration of the whole infra surface, "
            "which means everything except actual test files. Use only the provided repository metadata, repository summary, "
            "target framework characteristics, ruleset, target naming conventions, migration graph, suggested actions, "
            "and suggested target paths. The migration graph already contains the analyzer-computed topological order, so do not "
            "recompute ordering from scratch. suggestedAction and suggestedTargetPath are preliminary analyzer suggestions. "
            "You may override them if dependency structure or target framework architecture requires it. Each file starts as a "
            "migration unit, but you may split or merge units when the plan benefits from it. Do not split files unless they contain "
            "multiple logical classes or clearly separable domains. Produce only a migration plan that "
            "matches the planner_output_schema, not code. Preserve intent, avoid inventing repository facts, and optimize for safe incremental delivery."
        )

    @staticmethod
    def _build_migration_graph(
        migration_units: List[Dict[str, Any]],
        dependency_edges: List[Dict[str, str]],
    ) -> Dict[str, Any]:
        unit_by_source_path = {unit["source_path"]: unit for unit in migration_units}
        topological_order = [unit["id"] for unit in migration_units]
        dependency_pairs: List[List[int]] = []
        depends_on_map: Dict[int, List[int]] = {unit["id"]: [] for unit in migration_units}

        for edge in dependency_edges:
            source_unit = unit_by_source_path.get(edge["from"])
            target_unit = unit_by_source_path.get(edge["to"])
            if not source_unit or not target_unit:
                continue

            source_unit_id = source_unit["id"]
            target_unit_id = target_unit["id"]
            dependency_pairs.append([source_unit_id, target_unit_id])
            depends_on_map[source_unit_id].append(target_unit_id)

        return {
            "graph": {
                "edge_direction": "unit -> depends_on",
                "topological_order": topological_order,
                "dependency_edges": dependency_pairs,
            },
            "depends_on_map": depends_on_map,
        }

    @staticmethod
    def _build_planner_constraints() -> List[str]:
        return [
            "do_not_generate_code",
            "only_produce_plan",
            "plan_one_shot_infra_migration",
            "migrate_everything_except_actual_test_files",
            "respect_ruleset_target_structure",
            "consume_precomputed_topological_order",
            "avoid_creating_duplicate_utilities",
            "do_not_split_files_without_multiple_logical_classes_or_domains",
            "suggested_action_and_target_path_are_hints_not_final",
        ]

    @staticmethod
    def _build_planner_output_schema(workflow_scope: str) -> Dict[str, Any]:
        return {
            "migration_phase": workflow_scope,
            "planning_mode": "one_shot",
            "plan_summary": {
                "total_units": 0,
                "merges": 0,
                "splits": 0,
                "direct_migrations": 0,
            },
            "execution_order": [
                "migration_unit_id or planner_group_id"
            ],
            "plan_units": [
                {
                    "plan_unit_id": "string",
                    "source_migration_unit_ids": [123],
                    "decision": "migrate|copy|analyze_only|split|merge|skip",
                    "target_paths_final": ["string"],
                    "depends_on": ["plan_unit_id or migration_unit_id"],
                    "reason": "string",
                    "notes": ["string"],
                }
            ],
            "assumptions": ["string"],
            "risks": ["string"],
        }

    @staticmethod
    def _build_repository_summary(
        files: List[Dict[str, Any]],
        stored_summary: Dict[str, Any],
        source_repo_path: Path,
    ) -> Dict[str, Any]:
        role_counts: Dict[str, int] = {}
        total_files = stored_summary.get("total_files", len(files))
        category_split = stored_summary.get("category_split", {})
        infra_files = category_split.get("infra_files", 0)
        test_files = category_split.get("test_files", 0)

        for file in files:
            path = Path(file["path"])
            try:
                relative_path = path.relative_to(source_repo_path).as_posix()
            except ValueError:
                relative_path = path.as_posix()

            normalized_role = ContextBuilderService._normalize_file_role(relative_path, file["actual_role"])
            role_counts[normalized_role] = role_counts.get(normalized_role, 0) + 1

            if not category_split:
                if file["file_type"] == "test_file":
                    test_files += 1
                else:
                    infra_files += 1

        summary = {
            "total_files": total_files,
            "infra_files": infra_files,
            "test_files": test_files,
        }
        summary.update(role_counts)
        return summary

    def _build_target_naming_conventions(self) -> Dict[str, Any]:
        role_groups = {
            "test_files": "tests",
            "page_objects": "pages",
            "page_components": "components",
            "api_services": "services",
            "utilities": "utils",
            "base_classes": "fixtures",
            "config_files": "config",
            "config_properties": "config",
            "test_suite_config": "config",
            "report_config": "reporters",
            "test_data": "test-data",
        }

        conventions: Dict[str, Any] = {}
        for source_role, target_role in role_groups.items():
            template = self._build_target_file_template(target_role)
            folder = self._build_target_folder(target_role)
            conventions[source_role] = {
                "target_role": target_role,
                "target_folder": folder,
                "target_file_template": template,
            }

        conventions.update(
            {
                "repo_config": {
                    "target_role": "repo_root_or_docs",
                    "target_folder": ".",
                    "target_file_template": "{original-name}",
                },
                "build_config": {
                    "target_role": "analysis",
                    "target_folder": "analysis",
                    "target_file_template": "{original-name}",
                },
                "infra_resources": {
                    "target_role": "infra",
                    "target_folder": "infra",
                    "target_file_template": "{relative-source-name}",
                },
                "resource_files": {
                    "target_role": "resources",
                    "target_folder": "resources",
                    "target_file_template": "{original-name}",
                },
            }
        )

        return conventions

    def _build_target_metadata(
        self,
        file_path: str,
        normalized_role: str,
        suggested_target_path: str,
    ) -> Dict[str, str]:
        target_role = self._resolve_target_role(normalized_role, suggested_target_path)
        target_folder = self._build_target_folder(target_role, suggested_target_path)
        target_file_template = self._build_target_file_template(target_role, suggested_target_path)
        return {
            "target_role": target_role,
            "target_folder": target_folder,
            "target_file_template": target_file_template,
        }

    def _resolve_target_role(self, normalized_role: str, suggested_target_path: str) -> str:
        role_mapping = {
            "test_files": "tests",
            "page_objects": "pages",
            "page_components": "components",
            "api_services": "services",
            "utilities": "utils",
            "base_classes": "fixtures",
            "config_files": "config",
            "config_properties": "config",
            "test_suite_config": "config",
            "report_config": "reporters",
            "test_data": "test-data",
            "infra_resources": "infra",
            "resource_files": "resources",
        }
        if normalized_role in role_mapping:
            return role_mapping[normalized_role]

        normalized_target_path = suggested_target_path.replace("\\", "/")
        if normalized_target_path.startswith("docs/"):
            return "docs"
        if normalized_target_path.startswith("analysis/"):
            return "analysis"
        if normalized_target_path.startswith("infra/"):
            return "infra"
        if "/" not in normalized_target_path:
            return "repo_root"
        return "shared"

    def _build_target_folder(self, target_role: str, suggested_target_path: str | None = None) -> str:
        if suggested_target_path:
            normalized_target_path = suggested_target_path.replace("\\", "/")
            if "/" in normalized_target_path:
                return normalized_target_path.rsplit("/", 1)[0]
            return "."

        folder_mapping = {
            "tests": "src/tests/ui",
            "pages": "src/pages",
            "components": "src/pages/components",
            "services": "src/services",
            "utils": "src/utils",
            "fixtures": "src/fixtures",
            "config": "src/config",
            "test-data": "src/test-data",
            "reporters": "src/reporters",
            "docs": "docs",
            "analysis": "analysis",
            "infra": "infra",
            "resources": "resources",
            "repo_root": ".",
            "repo_root_or_docs": ".",
            "shared": "src/shared",
        }
        return folder_mapping.get(target_role, "src/shared")

    def _build_target_file_template(self, target_role: str, suggested_target_path: str | None = None) -> str:
        if suggested_target_path:
            normalized_target_path = suggested_target_path.replace("\\", "/")
            if target_role in {"repo_root", "docs", "analysis"}:
                return normalized_target_path.rsplit("/", 1)[-1]
            if target_role in {"infra", "resources"}:
                return "{relative-source-name}"

        naming_template_mapping = {
            "tests": "{kebab-name}.spec.ts",
            "pages": "{kebab-name}.page.ts",
            "components": "{kebab-name}.component.ts",
            "services": "{kebab-name}.service.ts",
            "utils": "{kebab-name}.ts",
            "fixtures": "{kebab-name}.ts",
            "config": "{kebab-name}.ts",
            "test-data": "{kebab-name}.ts",
            "reporters": "{kebab-name}.ts",
            "shared": "{kebab-name}.ts",
        }
        return naming_template_mapping.get(target_role, "{original-name}")

    @staticmethod
    def _build_repository_structure(source_repo_path: Path) -> Dict[str, Any]:
        def walk(directory: Path, depth: int = 0) -> Dict[str, Any]:
            if depth > 3:
                return {}

            tree: Dict[str, Any] = {}
            for child in sorted(directory.iterdir(), key=lambda item: (item.is_file(), item.name.lower())):
                if child.name in {".git", "node_modules", "target", "build", "dist", "__pycache__"}:
                    continue
                if child.is_dir():
                    tree[child.name] = walk(child, depth + 1)
                else:
                    tree[child.name] = "file"
            return tree

        return {
            "root": str(source_repo_path),
            "tree": walk(source_repo_path),
        }

    @staticmethod
    def _normalize_file_role(file_path: str, actual_role: str) -> str:
        normalized_path = file_path.replace("\\", "/").lower()
        file_name = normalized_path.rsplit("/", 1)[-1]

        if file_name in {"readme.md", "readme.txt"}:
            return "repo_config"

        if actual_role != "resource_files":
            return actual_role

        if file_name.endswith(".properties"):
            return "config_properties"

        if file_name.endswith(".xml") and (
            file_name.startswith("testng")
            or any(token in file_name for token in ("suite", "regression", "smoke", "sanity"))
        ):
            return "test_suite_config"

        if any(token in normalized_path for token in ("extent", "allure", "report", "spark")):
            return "report_config"

        if file_name.endswith((".xlsx", ".csv")) or any(
            token in normalized_path for token in ("testdata", "test-data", "data/", "dataset", "payload", "fixture")
        ):
            return "test_data"

        return "resource_files"

    @staticmethod
    def _normalize_suggested_migration(
        file_path: str,
        suggested_action: str,
        suggested_target_path: str,
    ) -> Dict[str, str]:
        normalized_path = file_path.replace("\\", "/").lower()
        file_name = normalized_path.rsplit("/", 1)[-1]

        if file_name in {"readme.md", "readme.txt"}:
            return {
                "suggested_action": "copy",
                "suggested_target_path": f"docs/{Path(file_path).name}",
            }

        return {
            "suggested_action": suggested_action,
            "suggested_target_path": suggested_target_path,
        }
