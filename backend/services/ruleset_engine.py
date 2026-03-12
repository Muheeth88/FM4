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
        kebab_name = re.sub(r'(?<!^)(?=[A-Z])', '-', clean_name).lower()
        
        # Apply suffix
        if suffix.startswith("."):
            target_filename = f"{kebab_name}{suffix}"
        else:
            # Handle cases like "Page.ts" -> "loginPage.ts" (though kebab is usually better)
            # If suffix is "Page.ts", maybe it wants "loginPage.ts" or "login-page.ts"
            # The YAML says "Page.ts" for pages.
            target_filename = f"{kebab_name}{suffix}"
        
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

