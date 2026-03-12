import fnmatch


class FileClassifier:

    def __init__(self, ruleset_engine):
        self.ruleset = ruleset_engine

    def classify(self, ast):

        path = ast["path"]
        annotations = ast.get("annotations", [])

        # Ruleset indicator matching
        classification = self.ruleset.ruleset.get("classification", {})

        for role, rule in classification.items():
            indicators = rule.get("indicators", [])
            for indicator in indicators:
                if indicator in str(ast): # Check in the whole AST result (imports, annotations, code)
                    return role

        # Fallback to pattern matching if available in classification (though not in current yaml)
        for role, rule in classification.items():
            patterns = rule.get("patterns", [])
            for pattern in patterns:
                if fnmatch.fnmatch(path, pattern):
                    return role

        # Heuristic
        if path.endswith("Utils.java"):
            return "utility"

        return "unknown"