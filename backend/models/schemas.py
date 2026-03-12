from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

class SourceConfig(BaseModel):
    framework: str
    language: str
    test_engine: str
    branch: str

class TargetConfig(BaseModel):
    framework: str
    language: str
    test_engine: str

class ProjectCreate(BaseModel):
    repo_url: str
    branch: str
    pat: Optional[str] = None

class ProjectResponse(BaseModel):
    id: str
    repo_url: str
    created_at: datetime
    status: str
    source: SourceConfig
    target: TargetConfig

class RepositoryVerification(BaseModel):
    repo_url: str
    pat: Optional[str] = None

class BranchResponse(BaseModel):
    name: str
    commit: str

class VerificationResponse(BaseModel):
    valid: bool
    message: str
    branches: Optional[List[BranchResponse]] = None
    error: Optional[str] = None
