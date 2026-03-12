import os

class MigrationUnitBuilder:

    def __init__(self, ruleset_engine, db):
        self.ruleset = ruleset_engine
        self.db = db

    def create_units(self, project_id, files, ordered_groups):
        file_map = {file["path"]: file for file in files}

        for file_type, order in ordered_groups.items():
            for iteration, path in enumerate(order):
                file = file_map[path]
                unit = {
                    "project_id": project_id,
                    "source_path": path,
                    "actual_role": file["actual_role"],
                    "file_type": file["file_type"],
                    "import_alias": "",
                    "iteration": iteration,
                    "status": "pending"
                }
                self.db.insert_migration_unit(unit)
