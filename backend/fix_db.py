import sqlite3
from pathlib import Path

DATABASE_PATH = Path("d:/Workspace/FM4/backend/migration.db")

def fix():
    conn = sqlite3.connect(str(DATABASE_PATH))
    cursor = conn.cursor()
    
    print("Dropping existing analysis tables to reset schema...")
    tables_to_drop = ["files", "dependencies", "migration_units", "repository_summary"]
    for table in tables_to_drop:
        cursor.execute(f"DROP TABLE IF EXISTS {table}")
    
    conn.commit()
    conn.close()
    print("Done. Now run init_db() via db.py to recreate them.")

if __name__ == "__main__":
    fix()
