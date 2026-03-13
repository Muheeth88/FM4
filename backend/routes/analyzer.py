from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
import logging
from typing import Dict, Any, List
from pathlib import Path
from database.db import get_db
from database.analyzer_db import AnalyzerDBWrapper
from services.ruleset_engine import RulesetEngine
from services.project_service import ProjectService
import os
import json

from services.source_analyzer.analyzer_service import AnalyzerService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/analyzer", tags=["analyzer"])

WORKSPACE_BASE = Path(__file__).parent.parent / "workspace"

@router.websocket("/{project_id}/ws")
async def analyze_websocket(websocket: WebSocket, project_id: str):
    await websocket.accept()
    
    project = ProjectService.get_project(project_id)
    if not project:
        await websocket.send_json({"error": "Project not found"})
        await websocket.close()
        return
        
    source_path = WORKSPACE_BASE / project_id / "source"
    if not source_path.exists():
        await websocket.send_json({"error": f"Source directory not found for project {project_id}"})
        await websocket.close()
        return

    async def progress_callback(status_data: dict):
        try:
            await websocket.send_json(status_data)
        except Exception as e:
            logger.error(f"Error sending websocket message: {e}")

    try:
        ruleset_engine = RulesetEngine() # Uses selenium_java_to_playwright_ts.yaml by default
        analyzer_db = AnalyzerDBWrapper()
        
        analyzer = AnalyzerService(ruleset_engine=ruleset_engine, db=analyzer_db)
        
        await analyzer.analyze_repository(
            project_id=project_id,
            repo_path=str(source_path),
            progress_callback=progress_callback
        )
        
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for project {project_id}")
    except Exception as e:
        logger.error(f"Error during analysis: {e}")
        try:
           await websocket.send_json({"error": str(e), "step": "Error", "status": "failed"})
        except:
           pass
    finally:
        try:
            await websocket.close()
        except:
            pass


@router.get("/{project_id}/report")
async def get_analysis_report(project_id: str):
    """Retrieve the summary and dependency details of the analysis report."""
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT summary_json FROM repository_summary WHERE project_id = ?", (project_id,))
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Analysis report not found for this project")
        
        summary = json.loads(row[0])
        
        # Add dependency graph and file details for the dashboard
        analyzer_db = AnalyzerDBWrapper()
        summary["dependencies"] = analyzer_db.get_dependencies(project_id)
        summary["files"] = analyzer_db.get_files(project_id)
        
        return summary
    except Exception as e:
        logger.error(f"Error fetching report: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
    finally:
        conn.close()

@router.get("/{project_id}/migration-units")
async def get_migration_units(project_id: str):
    """Retrieve all migration units for a project."""
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "SELECT id, source_path, actual_role, file_type, target_path, migration_action, status, iteration "
            "FROM migration_units WHERE project_id = ? ORDER BY file_type ASC, iteration ASC",
            (project_id,)
        )
        units = []
        for row in cursor.fetchall():
            units.append({
                "id": row[0],
                "source_path": row[1],
                "actual_role": row[2],
                "file_type": row[3],
                "migration_action": row[5],
                "status": row[6],
                "iteration": row[7]
            })
        return units
    except Exception as e:
        logger.error(f"Error fetching units: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
    finally:
        conn.close()
