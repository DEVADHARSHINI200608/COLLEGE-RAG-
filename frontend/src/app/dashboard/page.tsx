'use client';

import { useEffect, useState } from 'react';
import { useAuth } from '@/hooks/useAuth';
import { documentsAPI, chatAPI } from '@/lib/api';

export default function DashboardPage() {
  const { user, token } = useAuth();
  const [stats, setStats] = useState({ docs: 0, standardRes: 0, chats: 0 });
  const [modelStatus, setModelStatus] = useState<{ mode: string; is_local: boolean; local_available: boolean } | null>(null);

  useEffect(() => {
    if (!token) return;
    Promise.all([
      documentsAPI.list(token).catch(() => []),
      chatAPI.modelStatus(token).catch(() => null),
    ]).then(([docs, status]) => {
      setStats({
        docs: docs.length,
        standardRes: docs.filter((d: any) => d.is_standard_resource).length,
        chats: 0,
      });
      setModelStatus(status);
    });
  }, [token]);

  const roleLabel = { STUDENT: 'Student', FACULTY: 'Faculty Member', ADMIN: 'Administrator' }[user?.role || ''] || '';
  const roleColor = { STUDENT: 'var(--accent-blue)', FACULTY: 'var(--accent-purple)', ADMIN: 'var(--accent-primary)' }[user?.role || ''] || '';

  return (
    <div>
      {/* Header */}
      <div style={{ marginBottom: '32px' }}>
        <h1 style={{ fontSize: '28px', fontWeight: 800, letterSpacing: '-0.03em', marginBottom: '6px' }}>
          Welcome back, {user?.full_name?.split(' ')[0]} 👋
        </h1>
        <p style={{ color: 'var(--text-secondary)', fontSize: '14px' }}>
          Signed in as <span style={{ color: roleColor, fontWeight: 600 }}>{roleLabel}</span>
          {user?.department && ` • ${user.department}`}
        </p>
      </div>

      {/* AI Mode Banner */}
      {modelStatus && (
        <div className={`ai-mode-banner ${modelStatus.is_local ? 'ai-mode-local' : 'ai-mode-external'}`}>
          <span className="ai-mode-dot" />
          AI Mode: <strong>{modelStatus.is_local ? 'Local Model' : 'External AI'}</strong>
          {modelStatus.is_local && ' — Operating on locally hosted model'}
          {!modelStatus.is_local && ' — Connected to external AI service'}
        </div>
      )}

      {/* Stats */}
      <div className="stats-grid">
        {[
          { icon: '📄', value: stats.docs, label: 'Documents Indexed', color: 'rgba(99,102,241,0.15)' },
          { icon: '📖', value: stats.standardRes, label: 'Standard Resources', color: 'rgba(139,92,246,0.15)' },
          { icon: '🤖', value: 'Active', label: 'AI Agent Status', color: 'rgba(16,185,129,0.15)' },
          { icon: '🔐', value: user?.role, label: 'Access Level', color: 'rgba(245,158,11,0.15)' },
        ].map((s, i) => (
          <div key={i} className="stat-card">
            <div className="stat-icon" style={{ background: s.color }}>{s.icon}</div>
            <div className="stat-value">{s.value}</div>
            <div className="stat-label">{s.label}</div>
          </div>
        ))}
      </div>

      {/* Feature Cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '16px' }}>
        {[
          {
            icon: '🤖', title: 'Ask AI',
            desc: 'Query your documents using natural language. Supports multi-document analysis with source citations.',
            href: '/dashboard/chat', color: 'var(--accent-primary)',
            roles: ['STUDENT', 'FACULTY', 'ADMIN'],
          },
          {
            icon: '📤', title: 'Upload Documents',
            desc: 'Upload PDFs, PPTX, DOCX, CSV and more. Classify as confidential or educational.',
            href: '/dashboard/documents', color: 'var(--accent-purple)',
            roles: ['STUDENT', 'FACULTY', 'ADMIN'],
          },
          {
            icon: '📊', title: 'Multi-Doc Analysis',
            desc: 'Compare student lists, detect missing responses, count Yes/No answers deterministically.',
            href: '/dashboard/analysis', color: 'var(--accent-green)',
            roles: ['FACULTY', 'ADMIN'],
          },
          {
            icon: '📅', title: 'Deadlines',
            desc: 'Set response deadlines and receive automatic notifications for pending submissions.',
            href: '/dashboard/deadlines', color: 'var(--accent-amber)',
            roles: ['FACULTY', 'ADMIN'],
          },
          {
            icon: '📈', title: 'API Usage',
            desc: 'Monitor external AI usage, costs, fallback events, and model availability status.',
            href: '/dashboard/usage', color: 'var(--accent-red)',
            roles: ['ADMIN'],
          },
          {
            icon: '👥', title: 'User Management',
            desc: 'Manage user accounts, assign roles, and configure access permissions.',
            href: '/dashboard/users', color: 'var(--accent-blue)',
            roles: ['ADMIN'],
          },
        ]
          .filter(card => card.roles.includes(user?.role || ''))
          .map((card, i) => (
            <div
              key={i}
              className="card"
              style={{ cursor: 'pointer' }}
              onClick={() => window.location.href = card.href}
            >
              <div style={{
                width: '48px', height: '48px', borderRadius: '12px',
                background: `${card.color}20`,
                border: `1px solid ${card.color}30`,
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                fontSize: '22px', marginBottom: '16px',
              }}>{card.icon}</div>
              <h3 style={{ fontSize: '15px', fontWeight: 700, marginBottom: '8px' }}>{card.title}</h3>
              <p style={{ fontSize: '13px', color: 'var(--text-secondary)', lineHeight: 1.6 }}>{card.desc}</p>
              <div style={{
                marginTop: '16px', fontSize: '13px', color: card.color, fontWeight: 600,
                display: 'flex', alignItems: 'center', gap: '4px',
              }}>
                Open → 
              </div>
            </div>
          ))}
      </div>

      {/* Security notice */}
      <div style={{
        marginTop: '32px', padding: '16px 20px',
        background: 'rgba(99,102,241,0.06)',
        border: '1px solid rgba(99,102,241,0.15)',
        borderRadius: 'var(--radius-md)',
        display: 'flex', alignItems: 'flex-start', gap: '12px',
      }}>
        <span style={{ fontSize: '18px', flexShrink: 0, marginTop: '2px' }}>🔒</span>
        <div>
          <div style={{ fontSize: '13px', fontWeight: 600, marginBottom: '4px' }}>
            Multi-Layer Security Active
          </div>
          <div style={{ fontSize: '12px', color: 'var(--text-secondary)', lineHeight: 1.6 }}>
            All data access is enforced by role-based access control, source-level permissions, and retrieval-time metadata filtering.
            Confidential information is filtered before reaching the AI model.
          </div>
        </div>
      </div>
    </div>
  );
}
