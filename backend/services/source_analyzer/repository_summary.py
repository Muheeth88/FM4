class RepositorySummary:

    def __init__(self, db):
        self.db = db

    def generate(self, project_id):

        files = self.db.get_files(project_id)

        roles = {}
        categories = {
            "tests": 0,
            "helpers": 0
        }
        
        test_roles = ["test_files", "test_data"]

        for f in files:
            role = f["role"]

            if role not in roles:
                roles[role] = 0
            roles[role] += 1
            
            if role in test_roles:
                categories["tests"] += 1
            else:
                categories["helpers"] += 1

        summary = {
            "file_counts": roles,
            "category_split": categories,
            "total_files": len(files)
        }

        self.db.save_summary(project_id, summary)