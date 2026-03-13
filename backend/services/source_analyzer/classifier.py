import fnmatch


class FileClassifier:

    def __init__(self, ruleset_engine):
        self.ruleset = ruleset_engine

    def classify(self, ast):
        path = ast["path"]
        normalized_path = path.replace("\\", "/").lower()
        filename = normalized_path.rsplit("/", 1)[-1]
        classification = self.ruleset.ruleset.get("classification", {})

        if filename == "pom.xml":
            return "build_config"

        if filename == ".gitignore":
            return "repo_config"

        if "/infra/" in normalized_path or normalized_path.endswith("/infra"):
            return "infra_resources"

        if "/resources/" in normalized_path:
            return "resource_files"

        for role, rule in classification.items():
            for indicator in rule.get("indicators", []):
                if indicator in str(ast):
                    return role

        for role, rule in classification.items():
            for pattern in rule.get("patterns", []):
                if fnmatch.fnmatch(path, pattern):
                    return role

        return "unknown"

    def classify_file_type(self, ast, actual_role):
        if actual_role in {"build_config", "repo_config", "infra_resources", "resource_files", "config_files", "test_data"}:
            return "infra_file"

        if actual_role == "test_files":
            return "test_file"

        path = ast["path"].replace("\\", "/").lower()
        filename = path.rsplit("/", 1)[-1]
        source = str(ast).lower()

        if "@test" in source or "org.testng" in source or "junit" in source:
            return "test_file"

        if filename.endswith(".java"):
            basename = filename[:-5]
            if any(basename.endswith(token) for token in ("Test", "Tests", "Spec", "Suite", "IT")):
                return "test_file"

        return "infra_file"
