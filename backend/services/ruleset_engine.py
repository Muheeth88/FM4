import os
import yaml
from pathlib import Path
import re
from typing import Optional, Dict, Any

RULESETS_DIR = Path(__file__).parent.parent / "rulesets"

class RulesetEngine:
    """Orchestrates Ruleset loading and target path resolution."""

    def __init__(self, ruleset_name: str = "selenium_java_to_playwright_ts.yaml"):
        self.ruleset_name = ruleset_name
        self.ruleset = self._load_ruleset()

    def _load_ruleset(self) -> Dict[str, Any]:
        ruleset_path = RULESETS_DIR / self.ruleset_name
        if not ruleset_path.exists():
            raise FileNotFoundError(f"Ruleset not found: {ruleset_path}")
        with open(ruleset_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)

    def get_role_rules(self) -> Dict[str, Any]:
        """Returns the classification configuration block."""
        return self.ruleset.get("classification", {})

    def resolve_target_path_for_file(self, source_path: str, role: str) -> str:
        normalized_source = source_path.replace("\\", "/")
        lowercase_source = normalized_source.lower()
        filename = os.path.basename(normalized_source)

        if lowercase_source.endswith("/pom.xml"):
            return "analysis/pom.xml"

        if filename == ".gitignore":
            return ".gitignore"

        if filename.lower() in {"readme.md", "readme.txt"}:
            return f"docs/{filename}"

        if "/infra/" in lowercase_source:
            return f"infra/{normalized_source.split('/infra/', 1)[1]}"

        resources_marker = "/resources/"
        if resources_marker in lowercase_source:
            prefix, suffix = normalized_source.split("/resources/", 1)
            resources_root = prefix.split("/")[-1]
            if resources_root == "test":
                return f"src/test/resources/{suffix}"
            if resources_root == "main":
                return f"src/main/resources/{suffix}"
            return f"resources/{suffix}"

        return self.resolve_target_path(role, filename)

    def determine_migration_action(self, source_path: str, role: str) -> str:
        normalized_source = source_path.replace("\\", "/").lower()
        filename = normalized_source.rsplit("/", 1)[-1]

        if filename == "pom.xml":
            return "analyze_only"

        if filename in {".gitignore", "readme.md", "readme.txt"} or "/infra/" in normalized_source or "/resources/" in normalized_source:
            return "copy"

        return "migrate"

    def resolve_target_path(self, role: str, filename: str) -> str:
        """
        Resolves target path based on role and filename using the YAML schema.
        """
        classification = self.ruleset.get("classification", {})
        rule = classification.get(role, {})
        folder = rule.get("target_folder", "shared")
        
        naming = self.ruleset.get("naming", {})
        # Map roles to naming keys if possible
        naming_key = role
        if role == "test_files": naming_key = "tests"
        elif role == "page_objects": naming_key = "pages"
        elif role == "page_components": naming_key = "components"
        elif role == "api_services": naming_key = "services"
        elif role == "utilities": naming_key = "utils"
        
        naming_rule = naming.get(naming_key, {})
        suffix = naming_rule.get("suffix", ".ts")
        
        # Determine base name without extension and role suffix
        basename = filename.split('.')[0]
        # Remove common suffixes like 'Page', 'Test', 'Spec'
        clean_name = re.sub(r'(Page|Test|Spec)$', '', basename)
        
        # Convert to kebab case
        kebab_name = self._to_kebab_case(clean_name)
        normalized_suffix = self._normalize_suffix(suffix)
        
        # Apply suffix
        if normalized_suffix.startswith("."):
            target_filename = f"{kebab_name}{normalized_suffix}"
        else:
            target_filename = f"{kebab_name}{normalized_suffix}"
        
        # Compose path (following the YAML target_structure convention where 'src' is the root for code)
        target_path = os.path.join("src", folder, target_filename).replace('\\', '/')
        return target_path

    def get_import_alias(self, target_path: str) -> str:
        """Derives import alias based on the target path."""
        # Simple heuristic: e.g., src/pages/login.page.ts -> @pages/login.page
        path_without_ext = os.path.splitext(target_path)[0]
        # Check if it starts with src/
        if path_without_ext.startswith("src/"):
            parts = path_without_ext.split("/")
            if len(parts) >= 3: # e.g., src/pages/login.page
                folder = parts[1]
                filename = parts[-1]
                return f"@{folder}/{filename}"
        
        # Fallback to just the path
        return f"./{path_without_ext}"

    @staticmethod
    def _to_kebab_case(value: str) -> str:
        normalized = value.replace("_", "-")
        normalized = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1-\2", normalized)
        normalized = re.sub(r"([a-z0-9])([A-Z])", r"\1-\2", normalized)
        normalized = re.sub(r"-{2,}", "-", normalized)
        return normalized.strip("-").lower()

    def _normalize_suffix(self, suffix: str) -> str:
        if suffix.startswith("."):
            return suffix

        match = re.fullmatch(r"([A-Za-z0-9]+)\.ts", suffix)
        if not match:
            return suffix

        return f".{self._to_kebab_case(match.group(1))}.ts"

