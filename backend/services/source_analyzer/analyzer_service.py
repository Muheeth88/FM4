import logging
from pathlib import Path

from .repository_scanner import RepositoryScanner
from .ast_parser import ASTParser
from .classifier import FileClassifier
from .llm_role_classifier import LLMRoleClassifier
from .dependency_graph import DependencyGraphBuilder
from .migration_unit_builder import MigrationUnitBuilder
from .repository_summary import RepositorySummary

logger = logging.getLogger(__name__)


class AnalyzerService:

    def __init__(self, ruleset_engine, db):
        self.ruleset_engine = ruleset_engine
        self.db = db

        self.scanner = RepositoryScanner()
        self.parser = ASTParser()
        self.classifier = FileClassifier(ruleset_engine)
        self.llm_classifier = LLMRoleClassifier(ruleset_engine)
        self.graph_builder = DependencyGraphBuilder()
        self.unit_builder = MigrationUnitBuilder(ruleset_engine, db)
        self.summary_builder = RepositorySummary(db)

    async def analyze_repository(self, project_id, repo_path, progress_callback=None):
        import asyncio

        async def emit_progress(step_name, status="in_progress", message=""):
            if progress_callback:
                await progress_callback({
                    "step": step_name,
                    "status": status,
                    "message": message
                })

        logger.info("Starting repository analysis")
        await emit_progress("Initialization", "completed", "Started repository analysis")

        # Step 1 — Discover files
        await emit_progress("Discovering Files", "in_progress", "Scanning repository for source files")
        files = self.scanner.discover_files(repo_path)
        await asyncio.sleep(0.1)
        await emit_progress("Discovering Files", "completed", f"Found {len(files)} files")

        # Step 2 — Parse AST
        await emit_progress("Parsing AST", "in_progress", "Parsing Abstract Syntax Trees")
        ast_results = []
        for file in files:
            ast_data = self.parser.parse(file)
            ast_results.append(ast_data)
            await asyncio.sleep(0) # yield control
        await emit_progress("Parsing AST", "completed", f"Parsed {len(ast_results)} ASTs")

        # Step 3 — Classify files
        await emit_progress("Classifying Files", "in_progress", "Assigning roles to files")
        classified_files = []
        for ast in ast_results:
            actual_role = self.classifier.classify(ast)
            ast["actual_role"] = actual_role
            ast["actual_role_source"] = "deterministic"
            ast["file_type"] = self.classifier.classify_file_type(ast, actual_role)
            classified_files.append(ast)
            await asyncio.sleep(0) # yield control

        await emit_progress("Classifying Files", "completed", "Deterministic classification complete")

        # Step 4 — Build dependency graph
        unknown_files = [file for file in classified_files if file.get("actual_role") == "unknown"]
        if unknown_files:
            await emit_progress(
                "LLM Classification",
                "in_progress",
                f"Resolving {len(unknown_files)} unknown files with LLM",
            )
            llm_result = await asyncio.to_thread(self.llm_classifier.classify_unknown_files_with_traces, unknown_files)
            llm_stats = llm_result["stats"]
            for trace in llm_result["traces"]:
                if progress_callback:
                    await progress_callback(trace)
            if not self.llm_classifier.is_enabled():
                llm_message = "Skipped because OPENAI_API_KEY is not configured"
            else:
                llm_message = (
                    f"Resolved {llm_stats['resolved']} files, "
                    f"{llm_stats['remaining_unknown']} remain unknown"
                )
            await emit_progress("LLM Classification", "completed", llm_message)
        else:
            await emit_progress("LLM Classification", "completed", "No unknown files required LLM classification")

        for file in classified_files:
            if file.get("actual_role") == "unknown":
                file["actual_role"] = "utilities"
                file["actual_role_source"] = "fallback"

            refined_role = self._refine_role(file)
            if refined_role != file.get("actual_role"):
                file["actual_role"] = refined_role
                file["actual_role_source"] = "analyzer_refinement"

            file["file_type"] = self.classifier.classify_file_type(file, file["actual_role"])

        self.db.clear_project_analysis(project_id)
        self.db.insert_files(project_id, classified_files)

        await emit_progress("Building Graph", "in_progress", "Constructing dependency graph")
        graph = self.graph_builder.build(classified_files)
        self.db.insert_dependencies(project_id, graph)
        await asyncio.sleep(0)
        await emit_progress("Building Graph", "completed", "Dependency graph built")

        # Step 5 — Topological sort
        await emit_progress("Topological Sort", "in_progress", "Sorting infra and test migration orders")
        ordered_groups = {
            "infra_file": self.graph_builder.topological_sort_for_role(graph, classified_files, "infra_file"),
            "test_file": self.graph_builder.topological_sort_for_role(graph, classified_files, "test_file"),
        }
        await asyncio.sleep(0)
        await emit_progress("Topological Sort", "completed", "Sorted dependencies")

        # Step 6 — Create migration units
        await emit_progress("Migration Units", "in_progress", "Creating migration units")
        self.unit_builder.create_units(
            project_id,
            classified_files,
            ordered_groups
        )
        await asyncio.sleep(0)
        await emit_progress("Migration Units", "completed", "Migration units stored")

        # Step 7 — Build repository summary
        await emit_progress("Generating Summary", "in_progress", "Aggregating file metrics")
        self.summary_builder.generate(project_id)
        await asyncio.sleep(0)
        await emit_progress("Generating Summary", "completed", "Summary generated")

        logger.info("Repository analysis completed")
        await emit_progress("Complete", "completed", "Repository analysis finished!")
        return True

    def _refine_role(self, file):
        current_role = file.get("actual_role")
        path = (file.get("path") or "").replace("\\", "/").lower()
        filename = Path(path).name.lower()
        basename = Path(filename).stem.lower()
        source_blob = self._build_source_blob(file)

        if self._looks_like_utility(path, basename, source_blob):
            return "utilities"

        return current_role

    @staticmethod
    def _build_source_blob(file):
        return " ".join(
            str(part).lower()
            for part in (
                file.get("source", ""),
                file.get("content_preview", ""),
                file.get("imports", []),
                file.get("classes", []),
            )
            if part
        )

    @staticmethod
    def _looks_like_utility(path, basename, source_blob):
        utility_suffixes = (
            "util",
            "utils",
            "helper",
            "helpers",
            "constants",
            "constant",
            "validator",
            "validators",
            "listener",
            "listeners",
            "factory",
            "formatter",
        )
        utility_path_tokens = (
            "/utils/",
            "/utility/",
            "/utilities/",
            "/constants/",
            "/common/",
            "/support/",
            "/helpers/",
        )
        utility_source_tokens = (
            "loggerfactory",
            "slf4j",
            "randomstringutils",
            "randomutil",
            "webdriverwait",
            "expectedconditions",
            "java.util.random",
        )

        if any(path_token in path for path_token in utility_path_tokens):
            return True

        if any(basename.endswith(token) for token in utility_suffixes):
            return True

        if any(token in source_blob for token in utility_source_tokens) and any(
            token in basename for token in ("util", "helper", "constant")
        ):
            return True

        return False
