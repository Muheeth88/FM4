class RepositorySummary:

    def __init__(self, db):
        self.db = db

    def generate(self, project_id):
        files = self.db.get_files(project_id)
        roles = {}
        categories = {
            "test_files": 0,
            "infra_files": 0
        }

        for f in files:
            actual_role = f["actual_role"]
            file_type = f["file_type"]

            if actual_role not in roles:
                roles[actual_role] = 0
            roles[actual_role] += 1
            
            if file_type == "test_file":
                categories["test_files"] += 1
            else:
                categories["infra_files"] += 1

        summary = {
            "file_counts": roles,
            "category_split": categories,
            "total_files": len(files)
        }

        self.db.save_summary(project_id, summary)
