import os

class MigrationUnitBuilder:

    def __init__(self, ruleset_engine, db):
        self.ruleset = ruleset_engine
        self.db = db

    def create_units(self, project_id, files, order):

        iteration = 0

        for path in order:
            file = next(f for f in files if f["path"] == path)
            role = file["role"]

            unit = {
                "project_id": project_id,
                "source_path": path,
                "role": role,
                "target_path": "",
                "import_alias": "",
                "iteration": iteration,
                "status": "pending"
            }

            self.db.insert_migration_unit(unit)
            iteration += 1