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
    
    # Files table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS files (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        project_id TEXT NOT NULL,
        path TEXT NOT NULL,
        role TEXT NOT NULL,
        FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
    )
    ''')

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

    # Migration Units table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS migration_units (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        project_id TEXT NOT NULL,
        source_path TEXT NOT NULL,
        role TEXT NOT NULL,
        target_path TEXT NOT NULL,
        import_alias TEXT,
        iteration INTEGER,
        status TEXT DEFAULT 'pending',
        FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
    )
    ''')

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

if __name__ == "__main__":
    init_db()
    print("Database initialized successfully")
