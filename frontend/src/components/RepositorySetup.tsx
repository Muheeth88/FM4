import { useState, useEffect } from 'react';
import { AlertCircle, CheckCircle, Loader } from 'lucide-react';
import { repositoryApi } from '../services/api';
import './RepositorySetup.css';

interface Branch {
  name: string;
  commit: string;
}

interface Config {
  framework: string;
  language: string;
  test_engine: string;
}

export default function RepositorySetup() {
  const [repoUrl, setRepoUrl] = useState('');
  const [pat, setPat] = useState('');
  const [branches, setBranches] = useState<Branch[]>([]);
  const [selectedBranch, setSelectedBranch] = useState('');
  const [loading, setLoading] = useState(false);
  const [verified, setVerified] = useState(false);
  const [error, setError] = useState('');
  const [sourceConfig, setSourceConfig] = useState<Config | null>(null);
  const [targetConfig, setTargetConfig] = useState<Config | null>(null);
  const [creating, setCreating] = useState(false);
  const [projectCreated, setProjectCreated] = useState(false);
  const [projectId, setProjectId] = useState('');

  useEffect(() => {
    loadConfigs();
  }, []);

  const loadConfigs = async () => {
    try {
      const [sourceRes, targetRes] = await Promise.all([
        repositoryApi.getSourceConfig(),
        repositoryApi.getTargetConfig(),
      ]);
      setSourceConfig(sourceRes.data);
      setTargetConfig(targetRes.data);
    } catch (err) {
      console.error('Failed to load configs:', err);
    }
  };

  const handleVerify = async () => {
    if (!repoUrl) {
      setError('Please enter a repository URL');
      return;
    }

    setLoading(true);
    setError('');
    setVerified(false);
    setBranches([]);

    try {
      const response = await repositoryApi.verify(repoUrl, pat || undefined);
      
      if (response.data.valid) {
        setBranches(response.data.branches);
        setVerified(true);
        if (response.data.branches.length > 0) {
          setSelectedBranch(response.data.branches[0].name);
        }
      } else {
        setError(response.data.error || 'Failed to verify repository');
      }
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to verify repository');
    } finally {
      setLoading(false);
    }
  };

  const handleCreateProject = async () => {
    if (!selectedBranch) {
      setError('Please select a branch');
      return;
    }

    setCreating(true);
    setError('');

    try {
      const response = await repositoryApi.createProject(repoUrl, selectedBranch, pat || undefined);
      setProjectId(response.data.id);
      setProjectCreated(true);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to create project');
    } finally {
      setCreating(false);
    }
  };


  if (projectCreated) {
    return (
      <div className="success-container">
        <div className="success-card">
          <CheckCircle className="success-icon" size={48} />
          <h2>Migration Project Created!</h2>
          <p className="project-id">Project ID: <strong>{projectId}</strong></p>
          <div className="project-structure">
            <h3>Project Structure Created:</h3>
            <p><code>workspace/{projectId}/source</code> - Repository cloned here</p>
            <p><code>workspace/{projectId}/target</code> - Generated files will go here</p>
          </div>
          <div className="button-group">
            <button
              className="btn btn-secondary"
              onClick={() => {
                setRepoUrl('');
                setPat('');
                setSelectedBranch('');
                setBranches([]);
                setVerified(false);
                setProjectCreated(false);
                setProjectId('');
              }}
            >
              Create Another Project
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="repository-setup-container">
      <div className="setup-card">
        <h1>Framework Migration Tool</h1>
        
        {/* Configuration Display */}
        <div className="config-display">
          <div className="config-section">
            <h3>Source Configuration</h3>
            {sourceConfig && (
              <div className="config-details">
                <p><strong>Framework:</strong> {sourceConfig.framework}</p>
                <p><strong>Language:</strong> {sourceConfig.language}</p>
                <p><strong>Test Engine:</strong> {sourceConfig.test_engine}</p>
              </div>
            )}
          </div>
          
          <div className="arrow">→</div>
          
          <div className="config-section">
            <h3>Target Configuration</h3>
            {targetConfig && (
              <div className="config-details">
                <p><strong>Framework:</strong> {targetConfig.framework}</p>
                <p><strong>Language:</strong> {targetConfig.language}</p>
                <p><strong>Test Engine:</strong> {targetConfig.test_engine}</p>
              </div>
            )}
          </div>
        </div>

        {/* Error Alert */}
        {error && (
          <div className="alert alert-error">
            <AlertCircle size={20} />
            <span>{error}</span>
          </div>
        )}

        {/* Repository URL Input */}
        <div className="form-group">
          <label htmlFor="repoUrl">Repository URL *</label>
          <div className="input-with-btn">
            <input
              id="repoUrl"
              type="text"
              placeholder="https://github.com/username/repository.git"
              value={repoUrl}
              onChange={(e) => setRepoUrl(e.target.value)}
              disabled={verified}
              onKeyPress={(e) => e.key === 'Enter' && handleVerify()}
            />
            <button
              className={`btn btn-verify ${loading ? 'loading' : ''}`}
              onClick={handleVerify}
              disabled={loading || !repoUrl || verified}
            >
              {loading ? (
                <>
                  <Loader size={18} className="spinner" />
                  Verifying...
                </>
              ) : verified ? (
                <>
                  <CheckCircle size={18} />
                  Verified
                </>
              ) : (
                'Verify'
              )}
            </button>
          </div>
        </div>

        {/* PAT Input */}
        <div className="form-group">
          <label htmlFor="pat">Personal Access Token (Optional)</label>
          <input
            id="pat"
            type="password"
            placeholder="Leave empty for public repositories"
            value={pat}
            onChange={(e) => setPat(e.target.value)}
            disabled={verified}
          />
          <small>Required for private repositories. GitHub PAT, GitLab token, etc.</small>
        </div>

        {/* Branch Selection */}
        {verified && branches.length > 0 && (
          <div className="form-group">
            <label htmlFor="branch">Select Branch *</label>
            <select
              id="branch"
              value={selectedBranch}
              onChange={(e) => setSelectedBranch(e.target.value)}
            >
              {branches.map((branch) => (
                <option key={branch.name} value={branch.name}>
                  {branch.name} ({branch.commit})
                </option>
              ))}
            </select>
          </div>
        )}

        {/* Create Project Button */}
        {verified && branches.length > 0 && (
          <div className="form-group">
            <button
              className="btn btn-primary btn-large"
              onClick={handleCreateProject}
              disabled={creating || !selectedBranch}
            >
              {creating ? (
                <>
                  <Loader size={20} className="spinner" />
                  Initiating Migration...
                </>
              ) : (
                'Initiate Migration'
              )}
            </button>
          </div>
        )}

        {/* No branches message */}
        {verified && branches.length === 0 && (
          <div className="alert alert-warning">
            <AlertCircle size={20} />
            <span>No branches found in the repository</span>
          </div>
        )}
      </div>
    </div>
  );
}
