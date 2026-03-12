import json
from typing import List, Dict, Any
from database.db import get_db
import logging

logger = logging.getLogger(__name__)

class AnalyzerDBWrapper:
    """Wrapper class providing the exact DB interface expected by AnalyzerService."""

    @staticmethod
    def clear_project_analysis(project_id: str):
        """Remove previous analysis artifacts so reruns replace, not append."""
        conn = get_db()
        cursor = conn.cursor()
        try:
            cursor.execute('DELETE FROM migration_units WHERE project_id = ?', (project_id,))
            cursor.execute('DELETE FROM dependencies WHERE project_id = ?', (project_id,))
            cursor.execute('DELETE FROM files WHERE project_id = ?', (project_id,))
            cursor.execute('DELETE FROM repository_summary WHERE project_id = ?', (project_id,))
            conn.commit()
        except Exception as e:
            logger.error(f"Error clearing analysis data: {e}")
            conn.rollback()
            raise
        finally:
            conn.close()
    
    @staticmethod
    def insert_files(project_id: str, classified_files: List[Dict[str, Any]]) -> List[int]:
        """Insert files and return their IDs (though analyzer doesn't strictly use IDs yet)"""
        conn = get_db()
        cursor = conn.cursor()
        ids = []
        try:
            for file in classified_files:
                cursor.execute('''
                INSERT INTO files (project_id, path, role)
                VALUES (?, ?, ?)
                ''', (project_id, file["path"], file["role"]))
                ids.append(cursor.lastrowid)
            conn.commit()
        except Exception as e:
            logger.error(f"Error inserting files: {e}")
            conn.rollback()
        finally:
            conn.close()
        return ids

    @staticmethod
    def insert_dependencies(project_id: str, graph):
        """Insert dependencies from a networkx DiGraph."""
        conn = get_db()
        cursor = conn.cursor()
        try:
            # graph is a networkx.DiGraph
            for source, target in graph.edges():
                cursor.execute('''
                INSERT INTO dependencies (project_id, from_file_path, to_file_path)
                VALUES (?, ?, ?)
                ''', (project_id, source, target))
            conn.commit()
        except Exception as e:
            logger.error(f"Error inserting dependencies: {e}")
            conn.rollback()
        finally:
            conn.close()

    @staticmethod
    def insert_migration_unit(unit: Dict[str, Any]):
        conn = get_db()
        cursor = conn.cursor()
        try:
            cursor.execute('''
            INSERT INTO migration_units (project_id, source_path, role, target_path, import_alias, iteration, status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                unit["project_id"],
                unit["source_path"],
                unit["role"],
                unit["target_path"],
                unit["import_alias"],
                unit["iteration"],
                unit["status"]
            ))
            conn.commit()
        except Exception as e:
            logger.error(f"Error inserting migration unit: {e}")
            conn.rollback()
        finally:
            conn.close()

    @staticmethod
    def get_files(project_id: str) -> List[Dict[str, Any]]:
        conn = get_db()
        cursor = conn.cursor()
        files = []
        try:
            cursor.execute('SELECT path, role FROM files WHERE project_id = ?', (project_id,))
            for row in cursor.fetchall():
                files.append({
                    "path": row[0],
                    "role": row[1]
                })
        except Exception as e:
            logger.error(f"Error getting files: {e}")
        finally:
            conn.close()
        return files

    @staticmethod
    def save_summary(project_id: str, summary: Dict[str, Any]):
        conn = get_db()
        cursor = conn.cursor()
        try:
            # Upsert
            cursor.execute('DELETE FROM repository_summary WHERE project_id = ?', (project_id,))
            cursor.execute('''
            INSERT INTO repository_summary (project_id, summary_json)
            VALUES (?, ?)
            ''', (project_id, json.dumps(summary)))
            conn.commit()
        except Exception as e:
            logger.error(f"Error saving summary: {e}")
            conn.rollback()
        finally:
            conn.close()

    @staticmethod
    def get_dependencies(project_id: str) -> List[Dict[str, str]]:
        conn = get_db()
        cursor = conn.cursor()
        deps = []
        try:
            cursor.execute('SELECT from_file_path, to_file_path FROM dependencies WHERE project_id = ?', (project_id,))
            for row in cursor.fetchall():
                deps.append({
                    "from": row[0],
                    "to": row[1]
                })
        except Exception as e:
            logger.error(f"Error getting dependencies: {e}")
        finally:
            conn.close()
        return deps
