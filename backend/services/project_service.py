import sqlite3
from typing import Optional, Dict, List
from database.db import get_db
import logging
import yaml
from pathlib import Path

logger = logging.getLogger(__name__)

WORKSPACE_BASE = Path(__file__).parent.parent / "workspace"
RULESETS_DIR = Path(__file__).parent.parent / "rulesets"

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
            
            # Initialize target structure
            if not ProjectService.setup_target_structure(project_id):
                logger.error(f"Failed to initialize target structure for project {project_id}")
                return False
            
            return True
        except Exception as e:
            logger.error(f"Failed to create project: {str(e)}")
            return False
    
    @staticmethod
    def setup_target_structure(project_id: str, ruleset_name: str = "selenium_java_to_playwright_ts.yaml") -> bool:
        """Initialize the target folder structure based on ruleset config"""
        try:
            ruleset_path = RULESETS_DIR / ruleset_name
            if not ruleset_path.exists():
                logger.error(f"Ruleset not found: {ruleset_path}")
                return False
            
            with open(ruleset_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            
            target_structure = config.get('target_structure', {})
            if not target_structure:
                logger.warning(f"No target_structure found in {ruleset_name}")
                return True
            
            target_path = WORKSPACE_BASE / project_id / "target"
            target_path.mkdir(parents=True, exist_ok=True)
            
            def create_recursive(current_path: Path, structure: dict):
                for name, content in structure.items():
                    new_path = current_path / name
                    new_path.mkdir(exist_ok=True)
                    
                    # Create .gitkeep to ensure the folder is tracked by Git
                    (new_path / ".gitkeep").touch()
                    
                    if isinstance(content, dict) and content:
                        create_recursive(new_path, content)
            
            create_recursive(target_path, target_structure)
            logger.info(f"Created target structure for project {project_id} using {ruleset_name}")
            return True
        except Exception as e:
            logger.error(f"Error setting up target structure: {str(e)}")
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
