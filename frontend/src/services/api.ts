import axios from 'axios';

const API_BASE_URL = 'http://localhost:8000/api';

export const repositoryApi = {
  verify: (repoUrl: string, pat?: string) =>
    axios.post(`${API_BASE_URL}/repository/verify`, {
      repo_url: repoUrl,
      pat: pat || null,
    }),

  createProject: (repoUrl: string, branch: string, pat?: string) =>
    axios.post(`${API_BASE_URL}/repository/create-project`, {
      repo_url: repoUrl,
      branch,
      pat: pat || null,
    }),

  listProjects: () =>
    axios.get(`${API_BASE_URL}/repository/projects`),

  getProject: (projectId: string) =>
    axios.get(`${API_BASE_URL}/repository/project/${projectId}`),

  getSourceConfig: () =>
    axios.get(`${API_BASE_URL}/repository/config/source`),

  getTargetConfig: () =>
    axios.get(`${API_BASE_URL}/repository/config/target`),
};

export const analyzerApi = {
  getReport: (projectId: string) =>
    axios.get(`${API_BASE_URL}/analyzer/${projectId}/report`),
    
  getMigrationUnits: (projectId: string) =>
    axios.get(`${API_BASE_URL}/analyzer/${projectId}/migration-units`),

  migrateInfra: (projectId: string) =>
    axios.post(`${API_BASE_URL}/analyzer/${projectId}/migrate-infra`),
};
