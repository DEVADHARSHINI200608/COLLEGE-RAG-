'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { authAPI } from '@/lib/api';

const ROLES = [
  {
    id: 'STUDENT',
    label: 'Student',
    icon: '🎓',
    desc: 'Access course materials, ask AI questions, view standard resources',
    color: 'var(--accent-blue)',
  },
  {
    id: 'FACULTY',
    label: 'Faculty',
    icon: '👨‍🏫',
    desc: 'Upload documents, analyze student responses, set deadlines',
    color: 'var(--accent-purple)',
  },
  {
    id: 'ADMIN',
    label: 'Admin',
    icon: '⚙️',
    desc: 'Full access — manage users, monitor API usage, view audit logs',
    color: 'var(--accent-primary)',
  },
];

export default function RegisterPage() {
  const router = useRouter();
  const [fullName, setFullName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [role, setRole] = useState('STUDENT');
  const [department, setDepartment] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [step, setStep] = useState<1 | 2>(1); // step 1: role, step 2: details

  const validateForm = () => {
    if (!fullName.trim()) return 'Full name is required.';
    if (!email.trim()) return 'Email is required.';
    if (password.length < 8) return 'Password must be at least 8 characters.';
    if (password !== confirmPassword) return 'Passwords do not match.';
    return null;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const validationError = validateForm();
    if (validationError) { setError(validationError); return; }

    setError('');
    setLoading(true);
    try {
      await authAPI.register({
        full_name: fullName.trim(),
        email: email.trim(),
        password,
        role,
        department: department.trim() || undefined,
      });
      // Auto-redirect to login with success message
      router.push('/?registered=1');
    } catch (err: any) {
      setError(err.message || 'Registration failed. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const selectedRole = ROLES.find(r => r.id === role)!;

  return (
    <div style={{
      minHeight: '100vh',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      background: 'radial-gradient(ellipse at 40% 0%, rgba(139,92,246,0.15) 0%, transparent 60%), var(--bg-primary)',
      padding: '24px',
    }}>
      {/* Background blobs */}
      <div style={{
        position: 'fixed', top: '5%', right: '8%', width: '350px', height: '350px',
        background: 'radial-gradient(circle, rgba(99,102,241,0.07) 0%, transparent 70%)',
        pointerEvents: 'none',
      }} />
      <div style={{
        position: 'fixed', bottom: '8%', left: '5%', width: '280px', height: '280px',
        background: 'radial-gradient(circle, rgba(139,92,246,0.06) 0%, transparent 70%)',
        pointerEvents: 'none',
      }} />

      <div style={{ width: '100%', maxWidth: '480px' }}>
        {/* Logo */}
        <div style={{ textAlign: 'center', marginBottom: '36px' }}>
          <div style={{
            width: '60px', height: '60px',
            background: 'linear-gradient(135deg, var(--accent-primary), var(--accent-purple))',
            borderRadius: '16px',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontSize: '26px', margin: '0 auto 14px',
            boxShadow: '0 8px 32px rgba(99,102,241,0.35)',
          }}>🎓</div>
          <h1 style={{ fontSize: '22px', fontWeight: 800, letterSpacing: '-0.03em', marginBottom: '4px' }}>
            Create your account
          </h1>
          <p style={{ color: 'var(--text-secondary)', fontSize: '13px' }}>
            College RAG Platform — Secure &amp; Intelligent AI
          </p>
        </div>

        <div className="card">
          {/* Step indicator */}
          <div style={{ display: 'flex', gap: '8px', marginBottom: '24px' }}>
            {[1, 2].map(s => (
              <div key={s} style={{
                flex: 1, height: '3px', borderRadius: '2px',
                background: step >= s ? 'var(--accent-primary)' : 'var(--border)',
                transition: 'background 0.3s',
              }} />
            ))}
          </div>

          {step === 1 && (
            <>
              <h2 style={{ fontSize: '16px', fontWeight: 700, marginBottom: '4px' }}>Select your role</h2>
              <p style={{ color: 'var(--text-secondary)', fontSize: '13px', marginBottom: '20px' }}>
                Choose the role that matches your position.
              </p>

              <div style={{ display: 'flex', flexDirection: 'column', gap: '10px', marginBottom: '24px' }}>
                {ROLES.map(r => (
                  <div
                    key={r.id}
                    onClick={() => setRole(r.id)}
                    style={{
                      padding: '14px 16px',
                      borderRadius: '10px',
                      border: `2px solid ${role === r.id ? r.color : 'var(--border)'}`,
                      background: role === r.id ? `${r.color}10` : 'var(--bg-input)',
                      cursor: 'pointer',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '14px',
                      transition: 'all 0.2s',
                    }}
                  >
                    <div style={{ fontSize: '28px', lineHeight: 1 }}>{r.icon}</div>
                    <div style={{ flex: 1 }}>
                      <div style={{ fontSize: '14px', fontWeight: 700, color: role === r.id ? r.color : 'var(--text-primary)', marginBottom: '3px' }}>
                        {r.label}
                      </div>
                      <div style={{ fontSize: '12px', color: 'var(--text-secondary)', lineHeight: 1.4 }}>
                        {r.desc}
                      </div>
                    </div>
                    <div style={{
                      width: '18px', height: '18px', borderRadius: '50%',
                      border: `2px solid ${role === r.id ? r.color : 'var(--border)'}`,
                      background: role === r.id ? r.color : 'transparent',
                      display: 'flex', alignItems: 'center', justifyContent: 'center',
                      flexShrink: 0,
                    }}>
                      {role === r.id && <div style={{ width: '6px', height: '6px', borderRadius: '50%', background: 'white' }} />}
                    </div>
                  </div>
                ))}
              </div>

              <button
                className="btn btn-primary"
                style={{ width: '100%', justifyContent: 'center' }}
                onClick={() => setStep(2)}
              >
                Continue as {selectedRole.label} →
              </button>
            </>
          )}

          {step === 2 && (
            <>
              {/* Role badge */}
              <div style={{
                display: 'inline-flex', alignItems: 'center', gap: '8px',
                padding: '6px 12px', borderRadius: '99px', marginBottom: '20px',
                background: `${selectedRole.color}15`,
                border: `1px solid ${selectedRole.color}40`,
              }}>
                <span>{selectedRole.icon}</span>
                <span style={{ fontSize: '12px', fontWeight: 600, color: selectedRole.color }}>
                  {selectedRole.label}
                </span>
                <button
                  onClick={() => setStep(1)}
                  style={{ background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', fontSize: '12px', padding: 0 }}
                >
                  change
                </button>
              </div>

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
                  <label className="form-label">Full Name</label>
                  <input
                    id="register-fullname"
                    className="form-input"
                    value={fullName}
                    onChange={e => setFullName(e.target.value)}
                    placeholder="e.g. Devadharshini Kumar"
                    required
                    autoFocus
                  />
                </div>

                <div className="form-group">
                  <label className="form-label">Email address</label>
                  <input
                    id="register-email"
                    type="email"
                    className="form-input"
                    value={email}
                    onChange={e => setEmail(e.target.value)}
                    placeholder="you@college.edu"
                    required
                  />
                </div>

                <div className="form-group">
                  <label className="form-label">Department <span style={{ color: 'var(--text-muted)', fontWeight: 400 }}>(optional)</span></label>
                  <input
                    id="register-department"
                    className="form-input"
                    value={department}
                    onChange={e => setDepartment(e.target.value)}
                    placeholder="e.g. Computer Science"
                  />
                </div>

                <div className="form-group">
                  <label className="form-label">Password</label>
                  <div style={{ position: 'relative' }}>
                    <input
                      id="register-password"
                      type={showPassword ? 'text' : 'password'}
                      className="form-input"
                      value={password}
                      onChange={e => setPassword(e.target.value)}
                      placeholder="Min. 8 characters"
                      required
                      style={{ paddingRight: '44px' }}
                    />
                    <button
                      type="button"
                      onClick={() => setShowPassword(s => !s)}
                      style={{
                        position: 'absolute', right: '12px', top: '50%', transform: 'translateY(-50%)',
                        background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer',
                        fontSize: '16px',
                      }}
                    >{showPassword ? '🙈' : '👁️'}</button>
                  </div>

                  {/* Password strength bar */}
                  {password && (
                    <div style={{ marginTop: '8px' }}>
                      <div style={{ display: 'flex', gap: '4px' }}>
                        {[1, 2, 3, 4].map(i => {
                          const strength = Math.min(
                            (password.length >= 8 ? 1 : 0) +
                            (/[A-Z]/.test(password) ? 1 : 0) +
                            (/[0-9]/.test(password) ? 1 : 0) +
                            (/[^A-Za-z0-9]/.test(password) ? 1 : 0), 4
                          );
                          const colors = ['var(--accent-red)', 'var(--accent-amber)', 'var(--accent-blue)', 'var(--accent-green)'];
                          return (
                            <div key={i} style={{
                              flex: 1, height: '3px', borderRadius: '2px',
                              background: i <= strength ? colors[strength - 1] : 'var(--border)',
                              transition: 'background 0.2s',
                            }} />
                          );
                        })}
                      </div>
                      <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '4px' }}>
                        {password.length < 8 ? 'Too short' :
                         (/[A-Z]/.test(password) && /[0-9]/.test(password) && /[^A-Za-z0-9]/.test(password)) ? '💪 Strong' :
                         (/[A-Z]/.test(password) && /[0-9]/.test(password)) ? 'Good' : 'Add uppercase + number'}
                      </div>
                    </div>
                  )}
                </div>

                <div className="form-group">
                  <label className="form-label">Confirm Password</label>
                  <input
                    id="register-confirm-password"
                    type={showPassword ? 'text' : 'password'}
                    className="form-input"
                    value={confirmPassword}
                    onChange={e => setConfirmPassword(e.target.value)}
                    placeholder="Re-enter password"
                    required
                    style={{
                      borderColor: confirmPassword && confirmPassword !== password
                        ? 'rgba(239,68,68,0.5)'
                        : confirmPassword && confirmPassword === password
                        ? 'rgba(16,185,129,0.5)'
                        : undefined,
                    }}
                  />
                  {confirmPassword && confirmPassword === password && (
                    <div style={{ fontSize: '11px', color: 'var(--accent-green)', marginTop: '4px' }}>✓ Passwords match</div>
                  )}
                </div>

                <div style={{ display: 'flex', gap: '10px', marginTop: '8px' }}>
                  <button
                    type="button"
                    className="btn btn-secondary"
                    style={{ flex: 1, justifyContent: 'center' }}
                    onClick={() => setStep(1)}
                  >
                    ← Back
                  </button>
                  <button
                    id="register-submit"
                    type="submit"
                    className="btn btn-primary"
                    style={{ flex: 2, justifyContent: 'center' }}
                    disabled={loading}
                  >
                    {loading ? '⏳ Creating account...' : '✅ Create Account'}
                  </button>
                </div>
              </form>
            </>
          )}

          {/* Sign in link */}
          <div style={{
            marginTop: '20px', textAlign: 'center',
            fontSize: '13px', color: 'var(--text-secondary)',
          }}>
            Already have an account?{' '}
            <Link
              href="/"
              style={{ color: 'var(--accent-primary)', fontWeight: 600, textDecoration: 'none' }}
            >
              Sign In
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}
