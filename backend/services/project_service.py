import sqlite3
from typing import Optional, Dict, List
from database.db import get_db
import logging

logger = logging.getLogger(__name__)

class ProjectService:
    """Service for project database operations"""
    
    @staticmethod
    def create_project(project_id: str, repo_url: str, branch: str, 
                      source_framework: str, source_language: str, source_test_engine: str,
                      target_framework: str, target_language: str, target_test_engine: str) -> bool:
        """Create a new migration project"""
        try:
            conn = get_db()
            cursor = conn.cursor()
            
            # Insert project
            cursor.execute('''
            INSERT INTO projects (id, repo_url, status)
            VALUES (?, ?, ?)
            ''', (project_id, repo_url, 'created'))
            
            # Insert source config
            cursor.execute('''
            INSERT INTO source_config (project_id, framework, language, test_engine, branch)
            VALUES (?, ?, ?, ?, ?)
            ''', (project_id, source_framework, source_language, source_test_engine, branch))
            
            # Insert target config
            cursor.execute('''
            INSERT INTO target_config (project_id, framework, language, test_engine)
            VALUES (?, ?, ?, ?)
            ''', (project_id, target_framework, target_language, target_test_engine))
            
            conn.commit()
            conn.close()
            logger.info(f"Project {project_id} created successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to create project: {str(e)}")
            return False
    
    @staticmethod
    def get_project(project_id: str) -> Optional[Dict]:
        """Get project details by ID"""
        try:
            conn = get_db()
            cursor = conn.cursor()
            
            # Get project
            cursor.execute('SELECT * FROM projects WHERE id = ?', (project_id,))
            project_row = cursor.fetchone()
            
            if not project_row:
                return None
            
            # Get source config
            cursor.execute('SELECT * FROM source_config WHERE project_id = ?', (project_id,))
            source_row = cursor.fetchone()
            
            # Get target config
            cursor.execute('SELECT * FROM target_config WHERE project_id = ?', (project_id,))
            target_row = cursor.fetchone()
            
            conn.close()
            
            project = {
                "id": project_row[0],
                "repo_url": project_row[1],
                "created_at": project_row[2],
                "status": project_row[3],
                "source": {
                    "framework": source_row[2],
                    "language": source_row[3],
                    "test_engine": source_row[4],
                    "branch": source_row[5]
                },
                "target": {
                    "framework": target_row[2],
                    "language": target_row[3],
                    "test_engine": target_row[4]
                }
            }
            
            return project
        except Exception as e:
            logger.error(f"Failed to get project: {str(e)}")
            return None
    
    @staticmethod
    def list_projects() -> List[Dict]:
        """List all projects"""
        try:
            conn = get_db()
            cursor = conn.cursor()
            
            cursor.execute('SELECT id FROM projects ORDER BY created_at DESC')
            project_ids = [row[0] for row in cursor.fetchall()]
            conn.close()
            
            projects = []
            for project_id in project_ids:
                project = ProjectService.get_project(project_id)
                if project:
                    projects.append(project)
            
            return projects
        except Exception as e:
            logger.error(f"Failed to list projects: {str(e)}")
            return []
    
    @staticmethod
    def delete_project(project_id: str) -> bool:
        """Delete a project"""
        try:
            conn = get_db()
            cursor = conn.cursor()
            
            # Delete all related configs first
            cursor.execute('DELETE FROM source_config WHERE project_id = ?', (project_id,))
            cursor.execute('DELETE FROM target_config WHERE project_id = ?', (project_id,))
            cursor.execute('DELETE FROM projects WHERE id = ?', (project_id,))
            
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            logger.error(f"Failed to delete project: {str(e)}")
            return False
