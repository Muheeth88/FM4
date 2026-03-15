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
                INSERT INTO files (project_id, path, actual_role, file_type)
                VALUES (?, ?, ?, ?)
                ''', (project_id, file["path"], file["actual_role"], file["file_type"]))
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
            INSERT INTO migration_units (project_id, source_path, actual_role, file_type, suggested_target_path, suggested_action, import_alias, iteration, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                unit["project_id"],
                unit["source_path"],
                unit["actual_role"],
                unit["file_type"],
                unit["suggested_target_path"],
                unit["suggested_action"],
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
            cursor.execute('SELECT path, actual_role, file_type FROM files WHERE project_id = ?', (project_id,))
            for row in cursor.fetchall():
                files.append({
                    "path": row[0],
                    "actual_role": row[1],
                    "file_type": row[2]
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

    @staticmethod
    def get_repository_summary(project_id: str) -> Dict[str, Any] | None:
        conn = get_db()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "SELECT summary_json FROM repository_summary WHERE project_id = ?",
                (project_id,),
            )
            row = cursor.fetchone()
            if not row:
                return None
            return json.loads(row[0])
        except Exception as e:
            logger.error(f"Error getting repository summary: {e}")
            return None
        finally:
            conn.close()

    @staticmethod
    def get_migration_units(project_id: str, file_type: str | None = None) -> List[Dict[str, Any]]:
        conn = get_db()
        cursor = conn.cursor()
        units = []
        try:
            query = (
                "SELECT id, source_path, actual_role, file_type, suggested_target_path, suggested_action, "
                "import_alias, iteration, status "
                "FROM migration_units WHERE project_id = ?"
            )
            params: list[Any] = [project_id]

            if file_type:
                query += " AND file_type = ?"
                params.append(file_type)

            query += " ORDER BY iteration ASC, id ASC"
            cursor.execute(query, params)

            for row in cursor.fetchall():
                units.append(
                    {
                        "id": row[0],
                        "source_path": row[1],
                        "actual_role": row[2],
                        "file_type": row[3],
                        "suggested_target_path": row[4],
                        "suggested_action": row[5],
                        "import_alias": row[6],
                        "iteration": row[7],
                        "status": row[8],
                    }
                )
        except Exception as e:
            logger.error(f"Error getting migration units: {e}")
        finally:
            conn.close()
        return units
