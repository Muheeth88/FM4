import { useState, useEffect } from 'react';
import { Trash2, Folder, GitBranch, Code, Layers, Activity } from 'lucide-react';
import { repositoryApi } from '../services/api';
import AnalysisReport from './AnalysisReport';
import './MigrationProjectList.css';

interface Config {
  framework: string;
  language: string;
  test_engine: string;
  branch?: string;
}

interface Project {
  id: string;
  repo_url: string;
  created_at: string;
  status: string;
  source: Config & { branch: string };
  target: Config;
}

export default function MigrationProjectList() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [activeProject, setActiveProject] = useState<string | null>(null);

  useEffect(() => {
    loadProjects();
  }, []);

  const loadProjects = async () => {
    setLoading(true);
    setError('');
    try {
      const response = await repositoryApi.listProjects();
      setProjects(response.data);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to load projects');
    } finally {
      setLoading(false);
    }
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  if (loading) {
    return (
      <div className="projects-container">
        <div className="loading">Loading projects...</div>
      </div>
    );
  }

  if (activeProject) {
    return (
      <div className="projects-container">
        <button 
          className="btn btn-secondary" 
          onClick={() => setActiveProject(null)}
          style={{marginBottom: '20px'}}
        >
          &larr; Back to Projects
        </button>
        <AnalysisReport projectId={activeProject} />
      </div>
    );
  }

  return (
    <div className="projects-container">
      <div className="projects-header">
        <h1>Migration Projects</h1>
        <p className="projects-count">
          {projects.length} {projects.length === 1 ? 'project' : 'projects'} created
        </p>
      </div>

      {error && (
        <div className="alert alert-error">
          <span>{error}</span>
        </div>
      )}

      {projects.length === 0 ? (
        <div className="empty-state">
          <Folder size={48} />
          <h2>No Migration Projects Yet</h2>
          <p>Create a new migration project to get started</p>
        </div>
      ) : (
        <div className="projects-grid">
          {projects.map((project) => (
            <div key={project.id} className="project-card">
              <div className="project-header">
                <h3>{project.id}</h3>
                <span className="status-badge">{project.status}</span>
              </div>

              <div className="project-url">
                <a href={project.repo_url} target="_blank" rel="noopener noreferrer">
                  {project.repo_url}
                </a>
              </div>

              <div className="project-date">
                Created: {formatDate(project.created_at)}
              </div>

              <div className="config-row">
                <div className="config-item">
                  <div className="config-label">
                    <Layers size={16} />
                    Source
                  </div>
                  <div className="config-content">
                    <div>
                      <span className="config-label-small">Framework:</span> {project.source.framework}
                    </div>
                    <div>
                      <span className="config-label-small">Language:</span> {project.source.language}
                    </div>
                    <div>
                      <span className="config-label-small">Test Engine:</span> {project.source.test_engine}
                    </div>
                    <div>
                      <GitBranch size={14} style={{ display: 'inline', marginRight: '4px' }} />
                      <span className="config-label-small">Branch:</span> {project.source.branch}
                    </div>
                  </div>
                </div>

                <div className="arrow">→</div>

                <div className="config-item">
                  <div className="config-label">
                    <Code size={16} />
                    Target
                  </div>
                  <div className="config-content">
                    <div>
                      <span className="config-label-small">Framework:</span> {project.target.framework}
                    </div>
                    <div>
                      <span className="config-label-small">Language:</span> {project.target.language}
                    </div>
                    <div>
                      <span className="config-label-small">Test Engine:</span> {project.target.test_engine}
                    </div>
                  </div>
                </div>
              </div>

              <div className="project-paths">
                <div className="path-item">
                  <code>workspace/{project.id}/source</code>
                </div>
                <div className="path-item">
                  <code>workspace/{project.id}/target</code>
                </div>
              </div>

              <div className="project-actions">
                <button 
                  className="btn btn-primary"
                  onClick={() => setActiveProject(project.id)}
                  style={{marginRight: '12px'}}
                >
                  <Activity size={16} />
                  View Dashboard
                </button>
                <button className="btn-delete">
                  <Trash2 size={16} />
                  Delete Project
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
