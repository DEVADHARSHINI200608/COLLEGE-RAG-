'use client';

import { useAuth } from '@/hooks/useAuth';
import { useRouter, usePathname } from 'next/navigation';
import { useEffect, ReactNode } from 'react';

interface NavItem {
  label: string;
  icon: string;
  href: string;
  roles: string[];
  badge?: string;
}

const NAV_ITEMS: NavItem[] = [
  { label: 'Dashboard', icon: '🏠', href: '/dashboard', roles: ['STUDENT', 'FACULTY', 'ADMIN'] },
  { label: 'Ask AI', icon: '🤖', href: '/dashboard/chat', roles: ['STUDENT', 'FACULTY', 'ADMIN'] },
  { label: 'My Materials', icon: '📚', href: '/dashboard/materials', roles: ['STUDENT', 'FACULTY', 'ADMIN'] },
  { label: 'Standard Resources', icon: '📖', href: '/dashboard/resources', roles: ['STUDENT', 'FACULTY', 'ADMIN'] },
  { label: 'Documents', icon: '📄', href: '/dashboard/documents', roles: ['FACULTY', 'ADMIN'] },
  { label: 'Confidential Data', icon: '🔒', href: '/dashboard/confidential', roles: ['FACULTY', 'ADMIN'] },
  { label: 'Multi-Doc Analysis', icon: '📊', href: '/dashboard/analysis', roles: ['FACULTY', 'ADMIN'] },
  { label: 'Deadlines', icon: '📅', href: '/dashboard/deadlines', roles: ['FACULTY', 'ADMIN'] },
  { label: 'Notifications', icon: '🔔', href: '/dashboard/notifications', roles: ['FACULTY', 'ADMIN'] },
  { label: 'API Usage', icon: '📈', href: '/dashboard/usage', roles: ['ADMIN'] },
  { label: 'User Management', icon: '👥', href: '/dashboard/users', roles: ['ADMIN'] },
  { label: 'Settings', icon: '⚙️', href: '/dashboard/settings', roles: ['ADMIN'] },
];

const ROLE_COLORS: Record<string, string> = {
  STUDENT: 'var(--accent-blue)',
  FACULTY: 'var(--accent-purple)',
  ADMIN: 'var(--accent-primary)',
};

const ROLE_ICONS: Record<string, string> = {
  STUDENT: '🎓',
  FACULTY: '👨‍🏫',
  ADMIN: '⚙️',
};

export default function DashboardLayout({ children }: { children: ReactNode }) {
  const { user, token, isLoading, logout } = useAuth();
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    if (!isLoading && !token) router.push('/');
  }, [isLoading, token, router]);

  if (isLoading) return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: '100vh' }}>
      <div style={{ textAlign: 'center' }}>
        <div style={{ fontSize: '32px', marginBottom: '12px' }}>⏳</div>
        <p style={{ color: 'var(--text-secondary)' }}>Loading...</p>
      </div>
    </div>
  );

  if (!user) return null;

  const visibleNav = NAV_ITEMS.filter(item => item.roles.includes(user.role));

  return (
    <div className="app-shell">
      {/* Sidebar */}
      <aside className="sidebar">
        <div className="sidebar-header">
          <div className="sidebar-logo">
            <div className="sidebar-logo-icon">🎓</div>
            <div>
              <div className="sidebar-logo-text">RAG Platform</div>
              <div className="sidebar-logo-sub">Secure • Agentic • Intelligent</div>
            </div>
          </div>
        </div>

        <nav className="sidebar-nav">
          <div className="nav-section-label">Navigation</div>
          {visibleNav.map(item => (
            <button
              key={item.href}
              className={`nav-item ${pathname === item.href ? 'active' : ''}`}
              onClick={() => router.push(item.href)}
            >
              <span className="nav-icon">{item.icon}</span>
              {item.label}
              {item.badge && <span className="nav-badge">{item.badge}</span>}
            </button>
          ))}
        </nav>

        {/* User info at bottom */}
        <div style={{
          padding: '16px',
          borderTop: '1px solid var(--border)',
          background: 'var(--bg-card)',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '12px' }}>
            <div style={{
              width: '36px', height: '36px', borderRadius: '50%',
              background: `linear-gradient(135deg, ${ROLE_COLORS[user.role]}, var(--accent-purple))`,
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontSize: '16px', flexShrink: 0,
            }}>
              {ROLE_ICONS[user.role]}
            </div>
            <div style={{ overflow: 'hidden' }}>
              <div style={{ fontSize: '13px', fontWeight: 600, color: 'var(--text-primary)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {user.full_name}
              </div>
              <div style={{ fontSize: '11px', color: ROLE_COLORS[user.role], fontWeight: 600 }}>
                {user.role}
              </div>
            </div>
          </div>
          <button
            className="btn btn-secondary btn-sm"
            style={{ width: '100%', justifyContent: 'center' }}
            onClick={() => logout().then(() => router.push('/'))}
          >
            🚪 Sign Out
          </button>
        </div>
      </aside>

      {/* Main content */}
      <main className="main-content">
        {children}
      </main>
    </div>
  );
}
