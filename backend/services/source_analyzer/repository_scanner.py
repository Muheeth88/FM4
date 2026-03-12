import os

SUPPORTED_EXTENSIONS = [
    ".java",
    ".js",
    ".ts",
    ".py"
]


class RepositoryScanner:

    def discover_files(self, repo_path):

        discovered = []

        for root, dirs, files in os.walk(repo_path):

            for file in files:

                ext = os.path.splitext(file)[1]

                if ext not in SUPPORTED_EXTENSIONS:
                    continue

                full_path = os.path.join(root, file)

                discovered.append({
                    "path": full_path,
                    "name": file,
                    "extension": ext
                })

        return discovered