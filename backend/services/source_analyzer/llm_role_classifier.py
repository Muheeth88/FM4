import json
import logging
import os
import re
from typing import Any, Dict, List, Optional

from langchain_core.tools import tool

from services.llm import BaseLLMAgentService

logger = logging.getLogger(__name__)


class LLMRoleClassifier:
    """Resolves deterministic fallthroughs by classifying unknown files with an LLM."""

    def __init__(
        self,
        ruleset_engine,
        agent_service: Optional[BaseLLMAgentService] = None,
        batch_size: int = 25,
    ):
        self.ruleset_engine = ruleset_engine
        configured_batch_size = int(os.getenv("LLM_CLASSIFICATION_BATCH_SIZE", str(batch_size)))
        self.batch_size = max(1, configured_batch_size)
        self.allowed_roles = set(ruleset_engine.get_role_rules().keys())
        self.role_catalog = self._build_role_catalog()

        @tool
        def get_available_roles() -> str:
            """Return the allowed repository file roles and their rule hints."""
            return self.role_catalog

        self.agent_service = agent_service or BaseLLMAgentService(
            system_prompt=(
                "You classify repository files into one allowed migration role.\n"
                "Always call the get_available_roles tool before deciding.\n"
                "Choose exactly one closest supported role from the allowed roles.\n"
                "Classify the actual technical role of the file, not whether it is infra or test.\n"
                "Return only JSON with this schema: "
                '{"role":"<allowed role>","confidence":"low|medium|high","reason":"short explanation"}'
            ),
            tools=[get_available_roles],
            temperature=0,
        )

    def is_enabled(self) -> bool:
        return self.agent_service.is_enabled()

    def classify_unknown_files(self, files: List[Dict[str, Any]]) -> Dict[str, int]:
        return self.classify_unknown_files_with_traces(files)["stats"]

    def classify_unknown_files_with_traces(self, files: List[Dict[str, Any]]) -> Dict[str, Any]:
        stats = {
            "attempted": 0,
            "resolved": 0,
            "remaining_unknown": 0,
            "errors": 0,
        }
        traces: List[Dict[str, Any]] = []

        if not self.is_enabled():
            stats["remaining_unknown"] = sum(1 for file in files if file.get("actual_role") == "unknown")
            return {"stats": stats, "traces": traces}

        unknown_files = [file for file in files if file.get("actual_role") == "unknown"]
        for batch in self._chunk_files(unknown_files):
            stats["attempted"] += len(batch)
            try:
                batch_response = self.classify_batch(batch)
                batch_results = batch_response["results"]
                traces.append(batch_response["trace"])
                for index, file in enumerate(batch):
                    llm_result = batch_results.get(index)
                    if not llm_result:
                        llm_result = self._fallback_result(file, "Batch result missing for file")

                    actual_role = llm_result["role"]
                    file["actual_role_reason"] = llm_result.get("reason")
                    file["actual_role_confidence"] = llm_result.get("confidence", "low")
                    file["actual_role_source"] = "llm"
                    file["actual_role"] = actual_role
                    stats["resolved"] += 1
            except Exception as exc:
                logger.warning("LLM batch classification failed: %s", exc)
                stats["errors"] += len(batch)
                for file in batch:
                    fallback = self._fallback_result(file, f"LLM batch failed: {exc}")
                    file["actual_role"] = fallback["role"]
                    file["actual_role_reason"] = fallback["reason"]
                    file["actual_role_confidence"] = fallback["confidence"]
                    file["actual_role_source"] = "fallback"
                    stats["resolved"] += 1

        return {"stats": stats, "traces": traces}

    def classify_batch(self, files: List[Dict[str, Any]]) -> Dict[str, Any]:
        prompt = self._build_batch_prompt(files)
        response = self.agent_service.invoke_json_with_metadata(prompt)
        payload = response["output"]
        results = payload.get("results") if isinstance(payload, dict) else payload
        if not isinstance(results, list):
            raise ValueError("LLM batch output did not return a results array")

        classified = {}
        for item in results:
            if not isinstance(item, dict):
                continue
            index = item.get("index")
            if not isinstance(index, int) or index < 0 or index >= len(files):
                continue
            classified[index] = self._normalize_result(files[index], item)
        return {
            "results": classified,
            "trace": {
                "kind": "llm_trace",
                "operation": "unknown_file_batch_classification",
                "file_count": len(files),
                "files": [self._trim_path(file.get("path")) for file in files],
                "input": response["metadata"]["input_preview"],
                "output": payload,
                "raw_output": response["raw_output"],
                "model": response["metadata"]["model"],
                "duration_ms": response["metadata"]["duration_ms"],
                "usage": response["metadata"]["usage"],
                "response_id": response["metadata"]["response_id"],
                "finish_reason": response["metadata"]["finish_reason"],
            },
        }

    def classify(self, ast: Dict[str, Any]) -> Dict[str, str]:
        return self._normalize_result(ast, self.agent_service.invoke_json(self._build_prompt(ast)))

    def _normalize_result(self, ast: Dict[str, Any], result: Dict[str, Any]) -> Dict[str, str]:
        role = self._normalize_role(result.get("role"))
        if role in (None, "unknown"):
            role = self._fallback_role_from_context(ast)
        if role is None:
            raise ValueError(f"Unsupported role returned by LLM: {result.get('role')}")

        return {
            "role": role,
            "confidence": str(result.get("confidence", "low")).lower(),
            "reason": str(result.get("reason", "")).strip(),
        }

    def _build_prompt(self, ast: Dict[str, Any]) -> str:
        context = self._build_file_context(ast)
        return (
            "Classify this repository file.\n"
            "Use only the allowed roles from the tool output.\n"
            "Choose exactly one best-fit supported migration role.\n"
            "Do not return unknown for normal code inside this repository.\n"
            f"File context:\n{json.dumps(context, indent=2)}"
        )

    def _build_batch_prompt(self, files: List[Dict[str, Any]]) -> str:
        contexts = []
        for index, ast in enumerate(files):
            contexts.append({
                "index": index,
                **self._build_file_context(ast),
            })

        return (
            "Classify each repository file below.\n"
            "Use only the allowed roles from the tool output.\n"
            "Choose exactly one best-fit supported migration role for every file.\n"
            "Return JSON only with this schema: "
            '{"results":[{"index":0,"role":"<allowed role>","confidence":"low|medium|high","reason":"short explanation"}]}\n'
            f"Files:\n{json.dumps(contexts, indent=2)}"
        )

    def _build_file_context(self, ast: Dict[str, Any]) -> Dict[str, Any]:
        source = ast.get("source", "")
        classes = []
        for cls in ast.get("classes", [])[:10]:
            classes.append(
                {
                    "name": cls.get("name"),
                    "method_signatures": [self._compact_signature(method) for method in cls.get("methods", [])[:8]],
                }
            )

        return {
            "path": self._trim_path(ast.get("path")),
            "file_name": self._file_name(ast.get("path")),
            "package": self._extract_package(source),
            "path_hints": self._path_hints(ast.get("path")),
            "imports": [self._short_import(item) for item in ast.get("imports", [])[:8]],
            "classes": classes,
        }

    def _build_role_catalog(self) -> str:
        lines = []
        for role, config in self.ruleset_engine.get_role_rules().items():
            indicators = ", ".join(config.get("indicators", [])) or "none"
            target_folder = config.get("target_folder", "unknown")
            lines.append(f"{role}: indicators=[{indicators}], target_folder={target_folder}")
        return "\n".join(lines)

    def _normalize_role(self, role: Any) -> Optional[str]:
        if role is None:
            return None

        normalized = str(role).strip().lower()
        if normalized == "unknown":
            return "unknown"

        for allowed_role in self.allowed_roles:
            if allowed_role.lower() == normalized:
                return allowed_role

        return None

    def _fallback_role_from_context(self, ast: Dict[str, Any]) -> Optional[str]:
        path = (ast.get("path") or "").replace("\\", "/").lower()
        file_name = self._file_name(ast.get("path")).lower()
        source = (ast.get("source") or "").lower()

        if "@test" in source or "org.testng" in source or "junit" in source:
            return "test_files"
        if any(token in path for token in ("/api/",)) or any(token in file_name for token in ("api", "http", "request", "response")):
            return "api_services"
        if any(token in path for token in ("/exception/", "/utils/", "/support/", "/constants/")):
            return "utilities"
        if any(token in file_name for token in ("exception", "util", "helper", "validator", "listener")):
            return "utilities"
        if any(token in path for token in ("/beans/", "/testdata/")) or any(token in file_name for token in ("data", "details", "bean", "payload")):
            return "test_data"
        if any(token in file_name for token in ("base", "driver", "fixture")) or "/listeners/" in path:
            return "base_classes"
        if "/pages/components/" in path or "component" in file_name:
            return "page_components"
        if "/pages/" in path or "page" in file_name:
            return "page_objects"
        if "config" in file_name or "/config/" in path or ".properties" in path:
            return "config_files"
        return "utilities"

    def _fallback_result(self, ast: Dict[str, Any], reason: str) -> Dict[str, str]:
        role = self._fallback_role_from_context(ast)
        if role is None:
            raise ValueError(f"Unable to classify file {ast.get('path')}")
        return {
            "role": role,
            "confidence": "low",
            "reason": reason,
        }

    @staticmethod
    def _compact_signature(method_source: str) -> str:
        signature = method_source.strip().split("{", 1)[0].strip()
        return signature[:160]

    @staticmethod
    def _extract_package(source: str) -> str:
        match = re.search(r"package\s+([\w\.]+)\s*;", source)
        return match.group(1) if match else ""

    @staticmethod
    def _short_import(import_stmt: str) -> str:
        cleaned = import_stmt.replace("import", "").replace(";", "").strip()
        parts = [part for part in cleaned.split(".") if part]
        return ".".join(parts[-3:]) if len(parts) > 3 else cleaned

    @staticmethod
    def _path_hints(path: Optional[str]) -> List[str]:
        if not path:
            return []
        normalized = path.replace("\\", "/").lower()
        hints = []
        for token in ("actions", "api", "beans", "config", "constants", "exception", "listeners", "pages", "support", "testcases", "utils"):
            if f"/{token}/" in normalized:
                hints.append(token)
        return hints

    @staticmethod
    def _file_name(path: Optional[str]) -> str:
        if not path:
            return ""
        return path.replace("\\", "/").rsplit("/", 1)[-1]

    @staticmethod
    def _trim_path(path: Optional[str]) -> str:
        if not path:
            return ""
        parts = path.replace("\\", "/").split("/")
        return "/".join(parts[-8:])

    def _chunk_files(self, files: List[Dict[str, Any]]) -> List[List[Dict[str, Any]]]:
        return [files[index:index + self.batch_size] for index in range(0, len(files), self.batch_size)]
