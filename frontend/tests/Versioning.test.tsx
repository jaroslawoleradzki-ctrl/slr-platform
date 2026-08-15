import { describe, it, expect } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { ProjectProvider } from '../src/context/ProjectContext';
import { Header } from '../src/components/layout/Header';
import { Sidebar } from '../src/components/layout/Sidebar';
import { AboutModal } from '../src/components/common/AboutModal';
import { APP_VERSION, RELEASE_STATUS, RUNTIME_MODE } from '../src/config/version';
import { parseAppVersion } from '../src/utils/versionParser';

describe('Application Versioning & Release Identity', () => {
  it('provides an application version constant', () => {
    expect(APP_VERSION).toBe('0.4.9');
    expect(RELEASE_STATUS).toBe('Development Preview');
    expect(RUNTIME_MODE).toBe('Live API / Persistent Storage');
  });

  it('validates version strings against SemVer format and returns development fallback on invalid input', () => {
    expect(parseAppVersion('0.1.0')).toBe('0.1.0');
    expect(parseAppVersion('0.1.1')).toBe('0.1.1');
    expect(parseAppVersion('  0.2.1  \n')).toBe('0.2.1');
    expect(parseAppVersion('1.0.0-rc.1')).toBe('1.0.0-rc.1');
    expect(parseAppVersion(null)).toBe('development');
    expect(parseAppVersion(undefined)).toBe('development');
    expect(parseAppVersion('')).toBe('development');
    expect(parseAppVersion('   ')).toBe('development');
    expect(parseAppVersion('v0.1.0')).toBe('development');
    expect(parseAppVersion('invalid_version')).toBe('development');
  });

  it('renders application version and runtime mode badge in Header', async () => {
    render(
      <ProjectProvider>
        <MemoryRouter>
          <Header />
        </MemoryRouter>
      </ProjectProvider>
    );

    expect(screen.getByText(new RegExp(`v${APP_VERSION}`, 'i'))).toBeInTheDocument();
    expect(screen.getByText(RUNTIME_MODE)).toBeInTheDocument();
  });

  it('renders application version in Sidebar footer', () => {
    render(
      <ProjectProvider>
        <MemoryRouter initialEntries={['/projects/lean_energy/dashboard']}>
          <Sidebar />
        </MemoryRouter>
      </ProjectProvider>
    );

    expect(screen.getByText(new RegExp(`SLR Platform v${APP_VERSION}`, 'i'))).toBeInTheDocument();
  });

  it('renders AboutModal with version, release status and domain truth notice', () => {
    render(<AboutModal isOpen={true} onClose={() => {}} />);

    expect(screen.getByText('O aplikacji — SLR Platform')).toBeInTheDocument();
    expect(screen.getByText(`v${APP_VERSION}`)).toBeInTheDocument();
    expect(screen.getByText('Development Preview')).toBeInTheDocument();
    expect(screen.getByText(RUNTIME_MODE)).toBeInTheDocument();
    expect(screen.getByText(/Backend pozostaje jedynym źródłem prawdy/i)).toBeInTheDocument();
    expect(screen.queryByText(/Commit SHA/i)).not.toBeInTheDocument();
  });

  it('opens AboutModal when "O aplikacji" button is clicked in Header', async () => {
    render(
      <ProjectProvider>
        <MemoryRouter>
          <Header />
        </MemoryRouter>
      </ProjectProvider>
    );

    const aboutBtn = screen.getByTitle('Informacje o aplikacji');
    expect(aboutBtn).toBeInTheDocument();
    fireEvent.click(aboutBtn);

    expect(await screen.findByText('O aplikacji — SLR Platform')).toBeInTheDocument();
  });
});
