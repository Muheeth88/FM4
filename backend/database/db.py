import sqlite3
from pathlib import Path
import os

DATABASE_PATH = Path(__file__).parent.parent / "migration.db"

def get_db():
    """Get database connection"""
    db = sqlite3.connect(str(DATABASE_PATH))
    db.row_factory = sqlite3.Row
    return db

def init_db():
    """Initialize database with tables"""
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    
    conn = get_db()
    cursor = conn.cursor()
    
    # Projects table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS projects (
        id TEXT PRIMARY KEY,
        repo_url TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        status TEXT DEFAULT 'created'
    )
    ''')
    
    # Source configuration table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS source_config (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        project_id TEXT NOT NULL,
        framework TEXT NOT NULL,
        language TEXT NOT NULL,
        test_engine TEXT NOT NULL,
        branch TEXT NOT NULL,
        FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
    )
    ''')
    
    # Target configuration table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS target_config (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        project_id TEXT NOT NULL,
        framework TEXT NOT NULL,
        language TEXT NOT NULL,
        test_engine TEXT NOT NULL,
        FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
    )
    ''')
    
    _ensure_files_table(cursor)

    # Dependencies table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS dependencies (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        project_id TEXT NOT NULL,
        from_file_path TEXT NOT NULL,
        to_file_path TEXT NOT NULL,
        FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
    )
    ''')

    _ensure_migration_units_table(cursor)

    # Repository Summary table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS repository_summary (
        project_id TEXT PRIMARY KEY,
        summary_json TEXT NOT NULL,
        FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
    )
    ''')

    conn.commit()
    conn.close()

def _ensure_migration_units_table(cursor):
    cursor.execute("SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'migration_units'")
    exists = cursor.fetchone() is not None

    if not exists:
        cursor.execute('''
        CREATE TABLE migration_units (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id TEXT NOT NULL,
            source_path TEXT NOT NULL,
            actual_role TEXT NOT NULL,
            file_type TEXT NOT NULL,
            suggested_target_path TEXT,
            suggested_action TEXT DEFAULT 'migrate',
            import_alias TEXT,
            iteration INTEGER,
            status TEXT DEFAULT 'pending',
            FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
        )
        ''')
        return

    cursor.execute("PRAGMA table_info(migration_units)")
    columns = [row[1] for row in cursor.fetchall()]
    desired_columns = ["id", "project_id", "source_path", "actual_role", "file_type", "suggested_target_path", "suggested_action", "import_alias", "iteration", "status"]

    if columns == desired_columns:
        return

    cursor.execute("ALTER TABLE migration_units RENAME TO migration_units_old")
    cursor.execute('''
    CREATE TABLE migration_units (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        project_id TEXT NOT NULL,
        source_path TEXT NOT NULL,
        actual_role TEXT NOT NULL,
        file_type TEXT NOT NULL,
        suggested_target_path TEXT,
        suggested_action TEXT DEFAULT 'migrate',
        import_alias TEXT,
        iteration INTEGER,
        status TEXT DEFAULT 'pending',
        FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
    )
    ''')

    old_columns = set(columns)
    if {"id", "project_id", "source_path", "iteration", "status"}.issubset(old_columns):
        if {"actual_role", "file_type", "import_alias", "suggested_target_path", "suggested_action"}.issubset(old_columns):
            cursor.execute('''
            INSERT INTO migration_units (id, project_id, source_path, actual_role, file_type, suggested_target_path, suggested_action, import_alias, iteration, status)
            SELECT id, project_id, source_path, actual_role, file_type, suggested_target_path, suggested_action, import_alias, iteration, status
            FROM migration_units_old
            ''')
        elif {"actual_role", "file_type", "import_alias", "target_path", "migration_action"}.issubset(old_columns):
            cursor.execute('''
            INSERT INTO migration_units (id, project_id, source_path, actual_role, file_type, suggested_target_path, suggested_action, import_alias, iteration, status)
            SELECT id, project_id, source_path, actual_role, file_type, target_path, migration_action, import_alias, iteration, status
            FROM migration_units_old
            ''')
        elif {"actual_role", "file_type", "import_alias"}.issubset(old_columns):
            cursor.execute('''
            INSERT INTO migration_units (id, project_id, source_path, actual_role, file_type, suggested_target_path, suggested_action, import_alias, iteration, status)
            SELECT id, project_id, source_path, actual_role, file_type, NULL AS suggested_target_path, 'migrate' AS suggested_action, import_alias, iteration, status
            FROM migration_units_old
            ''')
        elif {"actual_role", "file_type"}.issubset(old_columns):
            cursor.execute('''
            INSERT INTO migration_units (id, project_id, source_path, actual_role, file_type, suggested_target_path, suggested_action, import_alias, iteration, status)
            SELECT id, project_id, source_path, actual_role, file_type, NULL AS suggested_target_path, 'migrate' AS suggested_action, '' AS import_alias, iteration, status
            FROM migration_units_old
            ''')
        elif {"role", "import_alias"}.issubset(old_columns):
            cursor.execute('''
            INSERT INTO migration_units (id, project_id, source_path, actual_role, file_type, suggested_target_path, suggested_action, import_alias, iteration, status)
            SELECT id, project_id, source_path, role, 'infra_file', NULL AS suggested_target_path, 'migrate' AS suggested_action, import_alias, iteration, status
            FROM migration_units_old
            ''')
        elif "role" in old_columns:
            cursor.execute('''
            INSERT INTO migration_units (id, project_id, source_path, actual_role, file_type, suggested_target_path, suggested_action, import_alias, iteration, status)
            SELECT id, project_id, source_path, role, 'infra_file', NULL AS suggested_target_path, 'migrate' AS suggested_action, '' AS import_alias, iteration, status
            FROM migration_units_old
            ''')

    cursor.execute("DROP TABLE migration_units_old")

def _ensure_files_table(cursor):
    cursor.execute("SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'files'")
    exists = cursor.fetchone() is not None

    if not exists:
        cursor.execute('''
        CREATE TABLE files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id TEXT NOT NULL,
            path TEXT NOT NULL,
            actual_role TEXT NOT NULL,
            file_type TEXT NOT NULL,
            FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
        )
        ''')
        return

    cursor.execute("PRAGMA table_info(files)")
    columns = [row[1] for row in cursor.fetchall()]
    desired_columns = ["id", "project_id", "path", "actual_role", "file_type"]

    if columns == desired_columns:
        return

    cursor.execute("ALTER TABLE files RENAME TO files_old")
    cursor.execute('''
    CREATE TABLE files (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        project_id TEXT NOT NULL,
        path TEXT NOT NULL,
        actual_role TEXT NOT NULL,
        file_type TEXT NOT NULL,
        FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
    )
    ''')

    old_columns = set(columns)
    if {"id", "project_id", "path"}.issubset(old_columns):
        if {"actual_role", "file_type"}.issubset(old_columns):
            cursor.execute('''
            INSERT INTO files (id, project_id, path, actual_role, file_type)
            SELECT id, project_id, path, actual_role, file_type
            FROM files_old
            ''')
        elif "role" in old_columns:
            cursor.execute('''
            INSERT INTO files (id, project_id, path, actual_role, file_type)
            SELECT id, project_id, path, role, 'infra_file'
            FROM files_old
            ''')

    cursor.execute("DROP TABLE files_old")

if __name__ == "__main__":
    init_db()
    print("Database initialized successfully")
