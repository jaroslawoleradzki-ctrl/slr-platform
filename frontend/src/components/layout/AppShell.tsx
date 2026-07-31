import React, { useEffect } from 'react';
import { Outlet, useParams } from 'react-router-dom';
import { Header } from './Header';
import { Sidebar } from './Sidebar';
import { WorkflowStepper } from '../workflow/WorkflowStepper';
import { useProject } from '../../context/ProjectContext';

export const AppShell: React.FC = () => {
  const { projectId } = useParams<{ projectId?: string }>();
  const { activeProject, setActiveProjectId } = useProject();

  useEffect(() => {
    if (projectId && projectId !== activeProject?.id) {
      setActiveProjectId(projectId);
    }
  }, [projectId, activeProject?.id, setActiveProjectId]);

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        minHeight: '100vh',
        backgroundColor: 'var(--bg-primary)',
      }}
    >
      <Header />
      <WorkflowStepper />
      <div style={{ display: 'flex', flex: 1, overflow: 'hidden' }}>
        <Sidebar />
        <main
          style={{
            flex: 1,
            padding: '24px',
            overflowY: 'auto',
            maxHeight: 'calc(100vh - 100px)',
          }}
        >
          <Outlet />
        </main>
      </div>
    </div>
  );
};
