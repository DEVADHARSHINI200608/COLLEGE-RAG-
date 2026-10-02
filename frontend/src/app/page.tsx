'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/hooks/useAuth';

export default function LoginPage() {
  const { login } = useAuth();
  const router = useRouter();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      await login(email, password);
      router.push('/dashboard');
    } catch (err: any) {
      setError(err.message || 'Login failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{
      minHeight: '100vh',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      background: 'radial-gradient(ellipse at 60% 0%, rgba(99,102,241,0.15) 0%, transparent 60%), var(--bg-primary)',
      padding: '24px',
    }}>
      {/* Background decoration */}
      <div style={{
        position: 'fixed', top: '10%', left: '5%', width: '300px', height: '300px',
        background: 'radial-gradient(circle, rgba(99,102,241,0.08) 0%, transparent 70%)',
        pointerEvents: 'none',
      }} />
      <div style={{
        position: 'fixed', bottom: '10%', right: '5%', width: '400px', height: '400px',
        background: 'radial-gradient(circle, rgba(139,92,246,0.06) 0%, transparent 70%)',
        pointerEvents: 'none',
      }} />

      <div style={{ width: '100%', maxWidth: '420px' }}>
        {/* Logo */}
        <div style={{ textAlign: 'center', marginBottom: '40px' }}>
          <div style={{
            width: '64px', height: '64px',
            background: 'linear-gradient(135deg, var(--accent-primary), var(--accent-purple))',
            borderRadius: '16px',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontSize: '28px', margin: '0 auto 16px',
            boxShadow: '0 8px 32px rgba(99,102,241,0.4)',
          }}>🎓</div>
          <h1 style={{ fontSize: '24px', fontWeight: 800, letterSpacing: '-0.03em', marginBottom: '6px' }}>
            College RAG Platform
          </h1>
          <p style={{ color: 'var(--text-secondary)', fontSize: '14px' }}>
            Secure & Intelligent Agentic AI
          </p>
        </div>

        {/* Card */}
        <div className="card">
          <h2 style={{ fontSize: '18px', fontWeight: 700, marginBottom: '4px' }}>Welcome back</h2>
          <p style={{ color: 'var(--text-secondary)', fontSize: '13px', marginBottom: '24px' }}>
            Sign in to your account
          </p>

          {error && (
            <div style={{
              background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.3)',
              borderRadius: '8px', padding: '12px 14px', marginBottom: '20px',
              color: 'var(--accent-red)', fontSize: '13px',
            }}>
              ⚠️ {error}
            </div>
          )}

          <form onSubmit={handleSubmit}>
            <div className="form-group">
              <label className="form-label">Email address</label>
              <input
                type="email"
                className="form-input"
                value={email}
                onChange={e => setEmail(e.target.value)}
                placeholder="you@college.edu"
                required
                autoFocus
              />
            </div>
            <div className="form-group">
              <label className="form-label">Password</label>
              <input
                type="password"
                className="form-input"
                value={password}
                onChange={e => setPassword(e.target.value)}
                placeholder="••••••••"
                required
              />
            </div>
            <button
              type="submit"
              className="btn btn-primary"
              style={{ width: '100%', justifyContent: 'center', marginTop: '8px' }}
              disabled={loading}
            >
              {loading ? '⏳ Signing in...' : '🔐 Sign In'}
            </button>
          </form>

          {/* Role hints */}
          <div style={{
            marginTop: '24px', paddingTop: '20px', borderTop: '1px solid var(--border)',
            display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '8px',
          }}>
            {[
              { role: 'Student', icon: '🎓', color: 'var(--accent-blue)' },
              { role: 'Faculty', icon: '👨‍🏫', color: 'var(--accent-purple)' },
              { role: 'Admin', icon: '⚙️', color: 'var(--accent-primary)' },
            ].map(r => (
              <div key={r.role} style={{
                padding: '10px', background: 'var(--bg-input)',
                borderRadius: '8px', textAlign: 'center',
                border: '1px solid var(--border)',
              }}>
                <div style={{ fontSize: '18px', marginBottom: '4px' }}>{r.icon}</div>
                <div style={{ fontSize: '11px', fontWeight: 600, color: r.color }}>{r.role}</div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
