'use client';

import { useEffect, useState } from 'react';
import { useAuth } from '@/hooks/useAuth';
import { adminAPI } from '@/lib/api';

export default function APIUsagePage() {
  const { token, user } = useAuth();
  const [summary, setSummary] = useState<any>(null);
  const [recent, setRecent] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!token || user?.role !== 'ADMIN') return;
    Promise.all([
      adminAPI.apiUsageSummary(token),
      adminAPI.recentUsage(token),
    ]).then(([s, r]) => {
      setSummary(s);
      setRecent(r);
    }).finally(() => setLoading(false));
  }, [token, user]);

  if (loading) return <div style={{ padding: '40px', textAlign: 'center', color: 'var(--text-muted)' }}>⏳ Loading usage data...</div>;
  if (!summary) return <div style={{ color: 'var(--text-muted)' }}>No usage data available.</div>;

  const todayPct = summary.today?.usage_pct || 0;
  const monthPct = summary.month?.usage_pct || 0;

  return (
    <div>
      <div style={{ marginBottom: '28px' }}>
        <h1 style={{ fontSize: '24px', fontWeight: 800 }}>API Usage Dashboard</h1>
        <p style={{ color: 'var(--text-secondary)', fontSize: '13px', marginTop: '4px' }}>
          Monitor external AI usage, costs, and model status
        </p>
      </div>

      {/* Model Status */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '16px', marginBottom: '28px' }}>
        {[
          {
            title: 'AI Status',
            value: summary.current_model_mode,
            icon: summary.is_using_local ? '🏠' : '☁️',
            color: summary.is_using_local ? 'var(--accent-amber)' : 'var(--accent-green)',
            sub: summary.is_using_local ? 'Using local model' : 'External API active',
          },
          {
            title: 'Provider',
            value: summary.external_provider?.toUpperCase(),
            icon: '🔌',
            color: 'var(--accent-blue)',
            sub: 'Primary provider',
          },
          {
            title: 'Local Model',
            value: summary.local_model_available ? 'Ready' : 'Offline',
            icon: summary.local_model_available ? '✅' : '❌',
            color: summary.local_model_available ? 'var(--accent-green)' : 'var(--accent-red)',
            sub: 'Fallback status',
          },
          {
            title: 'Fallback Threshold',
            value: `${summary.fallback_threshold_pct}%`,
            icon: '⚡',
            color: 'var(--accent-purple)',
            sub: 'Switches to local model at this %',
          },
        ].map((s, i) => (
          <div key={i} className="stat-card">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
              <div>
                <div style={{ fontSize: '12px', color: 'var(--text-muted)', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: '8px' }}>{s.title}</div>
                <div style={{ fontSize: '22px', fontWeight: 800, color: s.color }}>{s.value}</div>
                <div style={{ fontSize: '12px', color: 'var(--text-secondary)', marginTop: '4px' }}>{s.sub}</div>
              </div>
              <div style={{ fontSize: '24px' }}>{s.icon}</div>
            </div>
          </div>
        ))}
      </div>

      {/* Usage Meters */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '20px', marginBottom: '24px' }}>
        {[
          { label: 'Today\'s Usage', pct: todayPct, tokens: summary.today?.tokens, cost: summary.today?.cost_usd, limit_tokens: summary.today?.token_limit, limit_cost: summary.today?.cost_limit_usd },
          { label: 'Monthly Usage', pct: monthPct, tokens: summary.month?.tokens, cost: summary.month?.cost_usd, limit_tokens: summary.month?.token_limit, limit_cost: summary.month?.cost_limit_usd },
        ].map((m, i) => (
          <div key={i} className="card">
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '14px' }}>
              <div className="card-title">{m.label}</div>
              <div style={{ fontSize: '20px', fontWeight: 800, color: m.pct > 80 ? 'var(--accent-red)' : 'var(--accent-primary)' }}>
                {m.pct.toFixed(1)}%
              </div>
            </div>
            <div className="progress-bar" style={{ marginBottom: '12px' }}>
              <div className={`progress-fill ${m.pct > 80 ? 'danger' : ''}`} style={{ width: `${Math.min(m.pct, 100)}%` }} />
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
              <div style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>
                <div style={{ color: 'var(--text-muted)', marginBottom: '2px' }}>Tokens Used</div>
                <strong style={{ color: 'var(--text-primary)' }}>{(m.tokens || 0).toLocaleString()}</strong>
                <span style={{ color: 'var(--text-muted)' }}>/{(m.limit_tokens || 0).toLocaleString()}</span>
              </div>
              <div style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>
                <div style={{ color: 'var(--text-muted)', marginBottom: '2px' }}>Est. Cost</div>
                <strong style={{ color: 'var(--text-primary)' }}>${(m.cost || 0).toFixed(4)}</strong>
                <span style={{ color: 'var(--text-muted)' }}>/${m.limit_cost}</span>
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Recent requests */}
      <div className="card">
        <div className="card-header">
          <div>
            <div className="card-title">Recent API Calls</div>
            <div className="card-subtitle">Latest {recent.length} requests</div>
          </div>
        </div>
        <table className="data-table">
          <thead>
            <tr>
              <th>Time</th>
              <th>Provider</th>
              <th>Model</th>
              <th>Tokens</th>
              <th>Cost</th>
              <th>Status</th>
              <th>Fallback</th>
            </tr>
          </thead>
          <tbody>
            {recent.map((r: any) => (
              <tr key={r.id}>
                <td style={{ fontFamily: 'var(--font-mono)', fontSize: '12px' }}>
                  {new Date(r.created_at).toLocaleTimeString()}
                </td>
                <td>{r.provider}</td>
                <td style={{ fontFamily: 'var(--font-mono)', fontSize: '12px' }}>{r.model}</td>
                <td>{r.total_tokens?.toLocaleString()}</td>
                <td>${r.estimated_cost_usd?.toFixed(5)}</td>
                <td>
                  <span style={{
                    padding: '2px 8px', borderRadius: '99px', fontSize: '11px', fontWeight: 600,
                    background: r.status === 'SUCCESS' ? 'rgba(16,185,129,0.1)' : 'rgba(239,68,68,0.1)',
                    color: r.status === 'SUCCESS' ? 'var(--accent-green)' : 'var(--accent-red)',
                  }}>{r.status}</span>
                </td>
                <td>{r.is_fallback ? <span style={{ color: 'var(--accent-amber)' }}>🏠 Local</span> : '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
