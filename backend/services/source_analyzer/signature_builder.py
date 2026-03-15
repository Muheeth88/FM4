import json
import re
from pathlib import Path
from typing import Any, Dict, List

from .ast_parser import ASTParser


class SourceSignatureBuilder:
    """Build structured planner-friendly signatures from source files."""

    def __init__(self):
        self.parser = ASTParser()

    def build_signature(self, file_path: str) -> Dict[str, Any]:
        try:
            file = self._build_file_descriptor(file_path)
            ast = self.parser.parse(file)
            return self._signature_from_ast(ast)
        except Exception as exc:
            file_name = Path(file_path).name
            return {
                "parser": "unavailable",
                "fileName": file_name,
                "error": str(exc),
            }

    def build_signatures(self, file_paths: List[str]) -> Dict[str, Dict[str, Any]]:
        return {file_path: self.build_signature(file_path) for file_path in file_paths}

    def _signature_from_ast(self, ast: Dict[str, Any]) -> Dict[str, Any]:
        classes = ast.get("classes") or []
        if classes:
            imports = [self._short_import(item) for item in ast.get("imports", [])[:12]]
            class_parts = []
            for cls in classes[:4]:
                class_parts.append(
                    {
                        "class_name": cls.get("name") or Path(ast.get("path", "")).stem,
                        "annotations": cls.get("annotations", [])[:12],
                        "method_names": [
                            method.get("name")
                            for method in cls.get("methods", [])[:20]
                            if method.get("name")
                        ],
                    }
                )

            return {
                "parser": ast.get("parser", "java"),
                "imports": imports,
                "classes": class_parts,
            }

        return self._build_generic_signature(ast)

    def _build_generic_signature(self, ast: Dict[str, Any]) -> Dict[str, Any]:
        path = ast.get("path", "")
        extension = Path(path).suffix.lower()
        preview = (ast.get("content_preview") or "").strip()
        file_name = Path(path).name

        if ast.get("is_binary"):
            return {
                "parser": "binary",
                "fileName": file_name,
                "size": ast.get("size", 0),
            }

        if file_name == "pom.xml" or extension == ".xml":
            return self._xml_signature(preview, file_name)
        if extension == ".json":
            return self._json_signature(preview, file_name)
        if extension in {".yaml", ".yml"}:
            return self._yaml_signature(preview, file_name)
        if extension == ".properties":
            return self._properties_signature(preview, file_name)
        if extension == ".md":
            return self._markdown_signature(preview, file_name)
        if extension == ".csv":
            return self._csv_signature(preview, file_name)

        return self._text_signature(preview, file_name)

    @staticmethod
    def _build_file_descriptor(file_path: str) -> Dict[str, str]:
        path = Path(file_path)
        return {
            "path": str(path),
            "name": path.name,
            "extension": path.suffix.lower(),
        }

    @staticmethod
    def _compact_signature(method_source: str) -> str:
        signature = method_source.strip().split("{", 1)[0].strip()
        signature = re.sub(r"\s+", " ", signature)
        return signature[:160]

    @staticmethod
    def _short_import(import_stmt: str) -> str:
        cleaned = import_stmt.replace("import", "").replace(";", "").strip()
        parts = [part for part in cleaned.split(".") if part]
        return ".".join(parts[-3:]) if len(parts) > 3 else cleaned

    @staticmethod
    def _xml_signature(preview: str, file_name: str) -> str:
        root_match = re.search(r"<([A-Za-z_][\w\-\.:]*)\b", preview)
        tags = re.findall(r"<([A-Za-z_][\w\-\.:]*)\b", preview)
        unique_tags = []
        for tag in tags:
            if tag.startswith("?") or tag in unique_tags:
                continue
            unique_tags.append(tag)
        root = root_match.group(1) if root_match else "unknown-root"
        return {
            "parser": "xml",
            "fileName": file_name,
            "rootTag": root,
            "tags": unique_tags[:12],
        }

    @staticmethod
    def _json_signature(preview: str, file_name: str) -> str:
        try:
            payload = json.loads(preview)
            if isinstance(payload, dict):
                keys = list(payload.keys())[:10]
                return {
                    "parser": "json",
                    "fileName": file_name,
                    "topLevelKeys": [str(key) for key in keys],
                }
            if isinstance(payload, list):
                first_type = type(payload[0]).__name__ if payload else "empty"
                return {
                    "parser": "json",
                    "fileName": file_name,
                    "arrayLengthHint": len(payload),
                    "firstItemType": first_type,
                }
        except Exception:
            pass
        return SourceSignatureBuilder._text_signature(preview, file_name)

    @staticmethod
    def _yaml_signature(preview: str, file_name: str) -> str:
        keys = []
        for line in preview.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or ":" not in stripped:
                continue
            if line.startswith((" ", "\t", "-")):
                continue
            keys.append(stripped.split(":", 1)[0].strip())
            if len(keys) == 10:
                break
        return {
            "parser": "yaml",
            "fileName": file_name,
            "topLevelKeys": keys,
        }

    @staticmethod
    def _properties_signature(preview: str, file_name: str) -> str:
        keys = []
        for line in preview.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith(("#", "!")):
                continue
            if "=" in stripped:
                keys.append(stripped.split("=", 1)[0].strip())
            elif ":" in stripped:
                keys.append(stripped.split(":", 1)[0].strip())
            if len(keys) == 10:
                break
        return {
            "parser": "properties",
            "fileName": file_name,
            "keys": keys,
        }

    @staticmethod
    def _markdown_signature(preview: str, file_name: str) -> str:
        headings = []
        for line in preview.splitlines():
            stripped = line.strip()
            if stripped.startswith("#"):
                headings.append(stripped.lstrip("#").strip())
            if len(headings) == 6:
                break
        return {
            "parser": "markdown",
            "fileName": file_name,
            "headings": headings,
        }

    @staticmethod
    def _csv_signature(preview: str, file_name: str) -> str:
        lines = [line.strip() for line in preview.splitlines() if line.strip()]
        if not lines:
            return {
                "parser": "csv",
                "fileName": file_name,
                "columns": [],
            }
        headers = [column.strip() for column in lines[0].split(",")]
        return {
            "parser": "csv",
            "fileName": file_name,
            "columns": headers[:10],
        }

    @staticmethod
    def _text_signature(preview: str, file_name: str) -> str:
        lines = []
        for line in preview.splitlines():
            stripped = re.sub(r"\s+", " ", line).strip()
            if stripped:
                lines.append(stripped)
            if len(lines) == 3:
                break
        return {
            "parser": "text",
            "fileName": file_name,
            "previewLines": lines,
        }
