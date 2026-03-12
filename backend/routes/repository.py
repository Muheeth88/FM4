from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect, BackgroundTasks
from models.schemas import (
    RepositoryVerification, VerificationResponse, BranchResponse,
    ProjectCreate, ProjectResponse
)
from services.git_service import GitService
from services.project_service import ProjectService
import logging
from typing import List, Dict
import asyncio
import json
from pathlib import Path
import os

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/repository", tags=["repository"])

# Source and Target configurations (hardcoded for now)
SOURCE_CONFIG = {
    "framework": "Selenium",
    "language": "Java",
    "test_engine": "TestNG"
}

TARGET_CONFIG = {
    "framework": "Playwright",
    "language": "TypeScript",
    "test_engine": "playwrighttest"
}

@router.post("/verify", response_model=VerificationResponse)
async def verify_repository(request: RepositoryVerification):
    """
    Verify repository URL and fetch branches
    """
    logger.info(f"Verifying repository: {request.repo_url}")
    
    result = GitService.verify_repository(request.repo_url, request.pat)
    
    if not result["valid"]:
        return VerificationResponse(
            valid=False,
            message=f"Failed to verify repository: {result['error']}",
            branches=None,
            error=result["error"]
        )
    
    return VerificationResponse(
        valid=True,
        message="Repository verified successfully",
        branches=result["branches"],
        error=None
    )

@router.post("/create-project", response_model=ProjectResponse)
async def create_project(request: ProjectCreate):
    """
    Create a new migration project:
    1. Clone the repository
    2. Save project details to database
    """
    logger.info(f"Creating project for repository: {request.repo_url}")
    
    try:
        # Clone repository
        clone_result = GitService.clone_repository(request.repo_url, request.branch, request.pat)
        
        if clone_result["error"]:
            raise HTTPException(status_code=400, detail=f"Failed to clone repository: {clone_result['error']}")
        
        project_id = clone_result["project_id"]
        
        # Save to database
        success = ProjectService.create_project(
            project_id=project_id,
            repo_url=request.repo_url,
            branch=request.branch,
            source_framework=SOURCE_CONFIG["framework"],
            source_language=SOURCE_CONFIG["language"],
            source_test_engine=SOURCE_CONFIG["test_engine"],
            target_framework=TARGET_CONFIG["framework"],
            target_language=TARGET_CONFIG["language"],
            target_test_engine=TARGET_CONFIG["test_engine"]
        )
        
        if not success:
            raise HTTPException(status_code=500, detail="Failed to save project to database")
        
        # Fetch and return project details
        project = ProjectService.get_project(project_id)
        
        if not project:
            raise HTTPException(status_code=500, detail="Failed to retrieve created project")
        
        return ProjectResponse(**project)
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating project: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to create project: {str(e)}")

@router.get("/projects", response_model=List[ProjectResponse])
async def list_projects():
    """List all migration projects"""
    projects = ProjectService.list_projects()
    return [ProjectResponse(**project) for project in projects]

@router.get("/project/{project_id}", response_model=ProjectResponse)
async def get_project(project_id: str):
    """Get project details by ID"""
    project = ProjectService.get_project(project_id)
    
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    return ProjectResponse(**project)

@router.get("/config/source")
async def get_source_config():
    """Get source configuration"""
    return SOURCE_CONFIG

@router.get("/config/target")
async def get_target_config():
    """Get target configuration"""
    return TARGET_CONFIG

