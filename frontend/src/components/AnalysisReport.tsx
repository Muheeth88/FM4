import { useState, useEffect, useMemo } from 'react';
import { analyzerApi } from '../services/api';
import { AlertCircle, FileText, Activity, Layers, Code, Share2 } from 'lucide-react';
import './AnalysisReport.css';

interface FileCounts {
  [role: string]: number;
}

interface CategorySplit {
  tests: number;
  helpers: number;
}

interface Dependency {
  from: string;
  to: string;
}

interface FileDetail {
  path: string;
  role: string;
}

interface Summary {
  file_counts: FileCounts;
  category_split: CategorySplit;
  total_files: number;
  dependencies: Dependency[];
  files: FileDetail[];
}

interface MigrationUnit {
  id: number;
  source_path: string;
  role: string;
  target_path: string;
  status: string;
  iteration: number;
}

export default function AnalysisReport({ projectId }: { projectId: string }) {
  const [summary, setSummary] = useState<Summary | null>(null);
  const [units, setUnits] = useState<MigrationUnit[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [activeTab, setActiveTab] = useState<'helpers' | 'tests'>('helpers');

  useEffect(() => {
    const fetchData = async () => {
      try {
        setLoading(true);
        const [reportRes, unitsRes] = await Promise.all([
          analyzerApi.getReport(projectId),
          analyzerApi.getMigrationUnits(projectId)
        ]);
        setSummary(reportRes.data);
        setUnits(unitsRes.data);
      } catch (err: any) {
        setError(err.response?.data?.detail || 'Failed to load analysis report');
      } finally {
        setLoading(false);
      }
    };
    
    fetchData();
  }, [projectId]);

  const testUnits = useMemo(() => 
    units.filter(u => u.role === 'test_files' || u.role === 'test_data'), 
  [units]);
  
  const helperUnits = useMemo(() => 
    units.filter(u => u.role !== 'test_files' && u.role !== 'test_data'), 
  [units]);

  const getDependenciesFor = (path: string) => {
    return summary?.dependencies.filter(d => d.from === path).map(d => d.to) || [];
  };

  if (loading) {
    return <div className="loading">Loading analysis dashboard...</div>;
  }

  if (error) {
    return (
      <div className="alert alert-error">
        <AlertCircle size={20} />
        <span>{error}</span>
      </div>
    );
  }

  const currentUnits = activeTab === 'helpers' ? helperUnits : testUnits;

  return (
    <div className="analysis-dashboard">
      <div className="dashboard-header">
        <h2><Activity size={24} /> Repository Analysis Report</h2>
        <span className="project-id-badge">Project: {projectId}</span>
      </div>

      <div className="dashboard-grid">
        <div className="stat-card total">
          <div className="stat-icon"><FileText /></div>
          <div className="stat-info">
            <h3>Total Files</h3>
            <p className="stat-number">{summary?.total_files || 0}</p>
          </div>
        </div>
        
        <div className="stat-card helper">
          <div className="stat-icon"><Layers /></div>
          <div className="stat-info">
            <h3>Helper Files</h3>
            <p className="stat-number">{summary?.category_split.helpers || 0}</p>
          </div>
        </div>

        <div className="stat-card test">
          <div className="stat-icon"><Code /></div>
          <div className="stat-info">
            <h3>Test Files</h3>
            <p className="stat-number">{summary?.category_split.tests || 0}</p>
          </div>
        </div>

        <div className="stat-card dependency">
          <div className="stat-icon"><Share2 /></div>
          <div className="stat-info">
            <h3>Inter-dependencies</h3>
            <p className="stat-number">{summary?.dependencies.length || 0}</p>
          </div>
        </div>
      </div>

      <div className="tabs-container">
        <button 
          className={`tab-btn ${activeTab === 'helpers' ? 'active' : ''}`}
          onClick={() => setActiveTab('helpers')}
        >
          Non-Test Files (Helpers)
          <span className="count-badge">{helperUnits.length}</span>
        </button>
        <button 
          className={`tab-btn ${activeTab === 'tests' ? 'active' : ''}`}
          onClick={() => setActiveTab('tests')}
        >
          Test Files
          <span className="count-badge">{testUnits.length}</span>
        </button>
      </div>

      <div className="units-section">
        <div className="section-header">
          <h3>
            {activeTab === 'helpers' ? 'Helper Migration Topography' : 'Test Migration Topography'}
          </h3>
          <p className="units-desc">
            {activeTab === 'helpers' 
              ? 'These files will be migrated together as core components.' 
              : 'These files will be migrated after core components are ready.'}
          </p>
        </div>
        
        <div className="table-responsive">
          <table className="units-table">
            <thead>
              <tr>
                <th>Order</th>
                <th>Role</th>
                <th>Source Path</th>
                <th>Dependencies</th>
              </tr>
            </thead>
            <tbody>
              {currentUnits.map((unit) => {
                const deps = getDependenciesFor(unit.source_path);
                return (
                  <tr key={unit.id}>
                    <td><span className="iteration-badge">{unit.iteration}</span></td>
                    <td><span className={`role-badge role-${unit.role.replace('_', '-')}`}>{unit.role}</span></td>
                    <td>
                      <div className="path-container">
                        <code className="path-code">{unit.source_path}</code>
                      </div>
                    </td>
                    <td>
                      <div className="target-info">
                        {deps.length > 0 ? (
                          <div className="dependencies-list">
                            <span className="label">Depends on:</span>
                            {deps.map((d, i) => (
                              <code key={i} className="dep-tag" title={d}>{d.split('/').pop()}</code>
                            ))}
                          </div>
                        ) : (
                          <span className="no-deps">-</span>
                        )}
                      </div>
                    </td>
                  </tr>
                );
              })}
              {currentUnits.length === 0 && (
                <tr>
                  <td colSpan={4} className="text-center empty-row">
                    No files found in this category.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
