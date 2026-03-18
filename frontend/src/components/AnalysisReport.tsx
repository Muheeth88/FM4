import React, { useState, useEffect, useMemo } from 'react';
import { analyzerApi } from '../services/api';
import { AlertCircle, FileText, Activity, Layers, Code, Share2, WandSparkles } from 'lucide-react';
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
  suggested_target_path: string;
  suggested_action: string;
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

  const [expandedIds, setExpandedIds] = useState<number[]>([]);

  const toggleExpand = (id: number) => {
    setExpandedIds((prev) => (prev.includes(id) ? prev.filter(x => x !== id) : [...prev, id]));
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
              <th>Role</th>
              <th>File Type</th>
            </tr>
          </thead>
          <tbody>
            {units.map((unit) => {
              const deps = getDependenciesFor(unit.source_path);
              const filename = unit.source_path.split(/[/\\]/).pop() || unit.source_path;
              const isExpanded = expandedIds.includes(unit.id);
              return (
                <React.Fragment key={unit.id}>
                  <tr key={unit.id} className="row-clickable" onClick={() => toggleExpand(unit.id)}>
                    <td><span className="iteration-badge">{unit.iteration}</span></td>
                    <td>
                      <div className="file-meta">
                        <strong>{filename}</strong>
                      </div>
                    </td>
                    <td><span className={`role-badge role-${unit.actual_role.replace('_', '-')}`}>{unit.actual_role}</span></td>
                    <td><span className={`type-badge type-${unit.file_type.replace('_', '-')}`}>{unit.file_type}</span></td>
                  </tr>

                  {isExpanded && (
                    <tr className="expanded-row" key={unit.id + '-expanded'}>
                      <td colSpan={4}>
                        <div className="expanded-content">
                          <div className="expanded-path">
                            <strong>Path:</strong>
                            <code className="path-code" style={{marginLeft: '10px'}}>{unit.source_path}</code>
                          </div>

                          <div className="expanded-path">
                            <strong>Target:</strong>
                            <code className="path-code" style={{marginLeft: '10px'}}>{unit.suggested_target_path || 'Not resolved'}</code>
                          </div>

                          <div className="expanded-path">
                            <strong>Action:</strong>
                            <code className="path-code" style={{marginLeft: '10px'}}>{unit.suggested_action}</code>
                          </div>

                          <div className="expanded-deps">
                            <strong>Dependencies:</strong>
                            {deps.length > 0 ? (
                              <div className="dependencies-list" style={{marginTop: '8px'}}>
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
                              <span className="no-deps">No dependencies</span>
                            )}
                          </div>
                        </div>
                      </td>
                    </tr>
                  )}
                </React.Fragment>
              );
            })}
            {units.length === 0 && (
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
  );
}

export default function AnalysisReport({ projectId }: { projectId: string }) {
  const [summary, setSummary] = useState<Summary | null>(null);
  const [units, setUnits] = useState<MigrationUnit[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [selectedRoleFilter, setSelectedRoleFilter] = useState<string | null>(null);
  const [isPreparingContext, setIsPreparingContext] = useState(false);
  const [isInvokingPlanner, setIsInvokingPlanner] = useState(false);
  const [isGeneratingCode, setIsGeneratingCode] = useState(false);
  const [contextMessage, setContextMessage] = useState('');
  const [currentPlan, setCurrentPlan] = useState<any | null>(null);

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

  const filteredUnits = useMemo(() => {
    if (!selectedRoleFilter) return units;
    return units.filter(u => u.actual_role === selectedRoleFilter);
  }, [units, selectedRoleFilter]);

  const testUnits = useMemo(
    () => filteredUnits.filter(u => u.file_type === 'test_file'),
    [filteredUnits]
  );

  const infraUnits = useMemo(
    () => filteredUnits.filter(u => u.file_type === 'infra_file'),
    [filteredUnits]
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

  const handleMigrateInfra = async () => {
    try {
      setIsPreparingContext(true);
      setContextMessage('');
      const response = await analyzerApi.migrateInfra(projectId);
      console.log('FM4 Context Builder Prompt:', response.data.prompt);
      console.log('FM4 Context Builder Payload:', response.data.context);
      setContextMessage('Context preparation completed. The final planner prompt has been logged to the browser console.');
    } catch (err: any) {
      setContextMessage(err.response?.data?.detail || 'Failed to prepare migration context.');
    } finally {
      setIsPreparingContext(false);
    }
  };

  const handleInvokePlanner = async () => {
    try {
      setIsInvokingPlanner(true);
      setContextMessage('');
      const response = await analyzerApi.invokePlanner(projectId);
      console.log('Planner Agent Response:', response.data.migration_plan);
      console.log('Planner Agent Telemetry:', response.data.telemetry);
      setCurrentPlan(response.data.migration_plan);
      setContextMessage('Planner Agent execution completed. Plan and Telemetry logged to console.');
    } catch (err: any) {
      setContextMessage(err.response?.data?.detail || 'Failed to execute planner agent.');
    } finally {
      setIsInvokingPlanner(false);
    }
  };

  const handleGenerateCode = async () => {
    if (!currentPlan) {
      setContextMessage('No plan available. Please run "Invoke Planner Agent" first.');
      return;
    }

    try {
      setIsGeneratingCode(true);
      setContextMessage('');
      const response = await analyzerApi.generateCode(projectId, currentPlan);
      console.log('Generate Code Response:', response.data.generation_results);
      setContextMessage('Code Generation completed. Check the target repository.');
    } catch (err: any) {
      setContextMessage(err.response?.data?.detail || 'Failed to generate code.');
    } finally {
      setIsGeneratingCode(false);
    }
  };

  return (
    <div className="analysis-dashboard">
      <div className="dashboard-header">
        <div className="header-copy">
          <p className="eyebrow">Repository Intelligence</p>
          <h2><Activity size={24} /> Repository Analysis Report</h2>
        </div>
        <div className="header-actions">
          <button
            className="context-action-btn"
            onClick={handleMigrateInfra}
            disabled={isPreparingContext || isInvokingPlanner || isGeneratingCode}
          >
            <WandSparkles size={16} />
            {isPreparingContext ? 'Preparing Context...' : 'Migrate Infra'}
          </button>
          <button
            className="context-action-btn"
            onClick={handleInvokePlanner}
            disabled={isPreparingContext || isInvokingPlanner || isGeneratingCode}
            style={{ marginLeft: '10px' }}
          >
            <WandSparkles size={16} />
            {isInvokingPlanner ? 'Invoking Planner...' : 'Invoke Planner Agent'}
          </button>
          <button
            className="context-action-btn"
            onClick={handleGenerateCode}
            disabled={isPreparingContext || isInvokingPlanner || isGeneratingCode || !currentPlan}
            style={{ marginLeft: '10px', backgroundColor: currentPlan ? '#10B981' : '#6B7280' }}
          >
            <Code size={16} />
            {isGeneratingCode ? 'Generating Code...' : 'Generate Code'}
          </button>
          <span className="project-id-badge">Project: {projectId}</span>
        </div>
      </div>

      {contextMessage && (
        <div className={`context-message ${contextMessage.startsWith('Failed') ? 'error' : 'success'}`}>
          {contextMessage}
        </div>
      )}

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
            <div
              key={role}
              className={`role-summary-card ${selectedRoleFilter === role ? 'active' : ''}`}
              onClick={() => setSelectedRoleFilter(prev => prev === role ? null : role)}
              style={{cursor: 'pointer'}}
              role="button"
            >
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
