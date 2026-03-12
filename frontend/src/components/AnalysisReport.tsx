import { useState, useEffect, useMemo } from 'react';
import { analyzerApi } from '../services/api';
import { AlertCircle, FileText, Activity, Layers, Code, Share2 } from 'lucide-react';
import './AnalysisReport.css';

interface FileCounts {
  [role: string]: number;
}

interface CategorySplit {
  test_files: number;
  infra_files: number;
}

interface Dependency {
  from: string;
  to: string;
  to_file_type?: string;
}

interface FileDetail {
  path: string;
  actual_role: string;
  file_type: string;
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
  actual_role: string;
  file_type: string;
  status: string;
  iteration: number;
}

function MigrationTable({
  title,
  description,
  units,
  dependencies,
}: {
  title: string;
  description: string;
  units: MigrationUnit[];
  dependencies: Dependency[];
}) {
  const getDependenciesFor = (path: string) => {
    return dependencies.filter(d => d.from === path);
  };

  return (
    <div className="units-section">
      <div className="section-header">
        <h3>{title}</h3>
        <p className="units-desc">{description}</p>
      </div>

      <div className="table-responsive">
        <table className="units-table">
          <thead>
            <tr>
              <th>Order</th>
              <th>Filename</th>
              <th>Path</th>
              <th>Actual Role</th>
              <th>File Type</th>
              <th>Dependencies</th>
            </tr>
          </thead>
          <tbody>
            {units.map((unit) => {
              const deps = getDependenciesFor(unit.source_path);
              const filename = unit.source_path.split(/[/\\]/).pop() || unit.source_path;
              return (
                <tr key={unit.id}>
                  <td><span className="iteration-badge">{unit.iteration}</span></td>
                  <td>
                    <div className="file-meta">
                      <strong>{filename}</strong>
                    </div>
                  </td>
                  <td>
                    <div className="path-container">
                      <code className="path-code path-secondary">{unit.source_path}</code>
                    </div>
                  </td>
                  <td><span className={`role-badge role-${unit.actual_role.replace('_', '-')}`}>{unit.actual_role}</span></td>
                  <td><span className={`type-badge type-${unit.file_type.replace('_', '-')}`}>{unit.file_type}</span></td>
                  <td>
                    <div className="target-info">
                      {deps.length > 0 ? (
                        <div className="dependencies-list">
                          <span className="label">Depends on:</span>
                          {deps.map((d, i) => (
                            <div key={i} className="dep-chip" title={d.to}>
                              <code className="dep-tag">{d.to.split('/').pop()}</code>
                              <span className={`dep-type ${d.to_file_type === 'test_file' ? 'test' : 'infra'}`}>
                                {d.to_file_type || 'unknown'}
                              </span>
                            </div>
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
            {units.length === 0 && (
              <tr>
                <td colSpan={6} className="text-center empty-row">
                  No files found in this category.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export default function AnalysisReport({ projectId }: { projectId: string }) {
  const [summary, setSummary] = useState<Summary | null>(null);
  const [units, setUnits] = useState<MigrationUnit[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

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

  const testUnits = useMemo(
    () => units.filter(u => u.file_type === 'test_file'),
    [units]
  );

  const infraUnits = useMemo(
    () => units.filter(u => u.file_type === 'infra_file'),
    [units]
  );

  const dependencyView = useMemo(() => {
    const typeMap = new Map(summary?.files.map(file => [file.path, file.file_type]) || []);
    return (summary?.dependencies || []).map(dep => ({
      ...dep,
      to_file_type: typeMap.get(dep.to) || 'unknown',
    }));
  }, [summary]);

  if (loading) {
    return <div className="loading">Loading analysis dashboard...</div>;
  }

  if (error || !summary) {
    return (
      <div className="alert alert-error">
        <AlertCircle size={20} />
        <span>{error || 'Failed to load analysis report'}</span>
      </div>
    );
  }

  return (
    <div className="analysis-dashboard">
      <div className="dashboard-header">
        <div className="header-copy">
          <p className="eyebrow">Repository Intelligence</p>
          <h2><Activity size={24} /> Repository Analysis Report</h2>
        </div>
        <span className="project-id-badge">Project: {projectId}</span>
      </div>

      <div className="dashboard-grid">
        <div className="stat-card total">
          <div className="stat-icon"><FileText /></div>
          <div className="stat-info">
            <h3>Total Files</h3>
            <p className="stat-number">{summary.total_files}</p>
          </div>
        </div>

        <div className="stat-card helper">
          <div className="stat-icon"><Layers /></div>
          <div className="stat-info">
            <h3>Infra Files</h3>
            <p className="stat-number">{summary.category_split.infra_files}</p>
          </div>
        </div>

        <div className="stat-card test">
          <div className="stat-icon"><Code /></div>
          <div className="stat-info">
            <h3>Test Files</h3>
            <p className="stat-number">{summary.category_split.test_files}</p>
          </div>
        </div>

        <div className="stat-card dependency">
          <div className="stat-icon"><Share2 /></div>
          <div className="stat-info">
            <h3>Inter-dependencies</h3>
            <p className="stat-number">{summary.dependencies.length}</p>
          </div>
        </div>
      </div>

      <div className="role-summary">
        <h3>Actual Role Breakdown</h3>
        <div className="role-summary-grid">
          {Object.entries(summary.file_counts).map(([role, count]) => (
            <div key={role} className="role-summary-card">
              <span className={`role-badge role-${role.replace('_', '-')}`}>{role}</span>
              <strong>{count}</strong>
            </div>
          ))}
        </div>
      </div>

      <MigrationTable
        title="Infra Migration Order"
        description="Infra files are migrated first. Their dependency graph excludes any dependency on test files."
        units={infraUnits}
        dependencies={dependencyView}
      />

      <MigrationTable
        title="Test Migration Order"
        description="Test files are ordered separately and can depend on infra files that are already migrated."
        units={testUnits}
        dependencies={dependencyView}
      />
    </div>
  );
}
