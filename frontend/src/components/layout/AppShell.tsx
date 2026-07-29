import React from 'react';
import { Outlet } from 'react-router-dom';
import { Header } from './Header';
import { Sidebar } from './Sidebar';
import { WorkflowStepper } from '../workflow/WorkflowStepper';

export const AppShell: React.FC = () => {
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
