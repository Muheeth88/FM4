import os

SUPPORTED_EXTENSIONS = {
    ".java",
    ".js",
    ".ts",
    ".py",
    ".xml",
    ".properties",
    ".json",
    ".yml",
    ".yaml",
    ".sql",
    ".txt",
    ".xlsx",
    ".csv",
    ".md",
}

SUPPORTED_FILENAMES = {
    "pom.xml",
    ".gitignore",
    "docker-compose.yml",
    "docker-compose.yaml",
    "package.json",
    "package-lock.json",
    "tsconfig.json",
    "playwright.config.ts",
    "README.md",
}

IGNORED_DIRECTORIES = {
    ".git",
    "node_modules",
    "target",
    "build",
    "dist",
    ".idea",
    ".vscode",
    "__pycache__",
}


class RepositoryScanner:

    def discover_files(self, repo_path):

        discovered = []

        for root, dirs, files in os.walk(repo_path):
            dirs[:] = [directory for directory in dirs if directory not in IGNORED_DIRECTORIES]
            normalized_root = root.replace("\\", "/").lower()

            for file in files:
                ext = os.path.splitext(file)[1]
                include_by_location = "/infra" in normalized_root or "/resources" in normalized_root
                include_by_name = file in SUPPORTED_FILENAMES
                include_by_extension = ext.lower() in SUPPORTED_EXTENSIONS

                if not (include_by_location or include_by_name or include_by_extension):
                    continue

                full_path = os.path.join(root, file)

                discovered.append({
                    "path": full_path,
                    "name": file,
                    "extension": ext.lower()
                })

        return discovered
