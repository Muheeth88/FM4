import os
import shutil
import uuid
from pathlib import Path
from git import Repo, GitCommandError
from typing import Optional, List, Dict
import logging

logger = logging.getLogger(__name__)

WORKSPACE_BASE = Path(__file__).parent.parent / "workspace"

class GitService:
    """Service for Git operations"""
    
    @staticmethod
    def verify_repository(repo_url: str, pat: Optional[str] = None) -> Dict:
        """
        Verify repository URL and access
        Returns: {valid: bool, branches: List[str], error: str}
        """
        try:
            # If PAT is provided, modify the URL
            auth_url = repo_url
            if pat:
                # Replace https://github.com/ with https://PAT@github.com/
                if "https://" in repo_url:
                    auth_url = repo_url.replace("https://", f"https://{pat}@")
            
            # Try to fetch remote branches without cloning
            repo = Repo.init(Path(WORKSPACE_BASE) / ".temp_verify")
            repo.create_remote("origin", auth_url)
            
            # Fetch references to get branches
            repo.remotes.origin.fetch()
            
            # Get branches
            branches = []
            for ref in repo.remotes.origin.refs:
                branch_name = ref.name.split("/")[-1]
                if branch_name != "HEAD":
                    branches.append({
                        "name": branch_name,
                        "commit": ref.commit.hexsha[:7]
                    })
            
            # Cleanup
            shutil.rmtree(str(Path(WORKSPACE_BASE) / ".temp_verify"), ignore_errors=True)
            
            return {
                "valid": True,
                "branches": branches,
                "error": None
            }
        except Exception as e:
            logger.error(f"Repository verification failed: {str(e)}")
            # Cleanup on error
            shutil.rmtree(str(Path(WORKSPACE_BASE) / ".temp_verify"), ignore_errors=True)
            return {
                "valid": False,
                "branches": [],
                "error": str(e)
            }
    
    @staticmethod
    def clone_repository(repo_url: str, branch: str, pat: Optional[str] = None) -> Dict:
        """
        Clone repository into workspace/{projectId}/source
        Returns: {project_id: str, source_path: str, target_path: str, error: str}
        """
        try:
            project_id = str(uuid.uuid4())[:8]
            
            # Create project directories
            project_dir = WORKSPACE_BASE / project_id
            source_dir = project_dir / "source"
            target_dir = project_dir / "target"
            
            source_dir.mkdir(parents=True, exist_ok=True)
            
            # Clone repository
            auth_url = repo_url
            if pat:
                if "https://" in repo_url:
                    auth_url = repo_url.replace("https://", f"https://{pat}@")
            
            logger.info(f"Cloning repository to {source_dir}")
            Repo.clone_from(auth_url, str(source_dir), branch=branch, depth=1)
            
            logger.info(f"Repository cloned successfully. Project ID: {project_id}")
            
            return {
                "project_id": project_id,
                "source_path": str(source_dir),
                "target_path": str(target_dir),
                "error": None
            }
        except Exception as e:
            logger.error(f"Repository cloning failed: {str(e)}")
            # Cleanup on error
            shutil.rmtree(str(project_dir), ignore_errors=True)
            return {
                "project_id": None,
                "source_path": None,
                "target_path": None,
                "error": str(e)
            }
    
    @staticmethod
    def get_project_path(project_id: str) -> Optional[Path]:
        """Get the project directory path"""
        project_dir = WORKSPACE_BASE / project_id
        if project_dir.exists():
            return project_dir
        return None
