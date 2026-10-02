'use client';

import { useEffect, useState } from 'react';
import { useAuth } from '@/hooks/useAuth';
import { deadlinesAPI } from '@/lib/api';

export default function NotificationsPage() {
  const { token } = useAuth();
  const [notifications, setNotifications] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!token) return;
    deadlinesAPI.notifications(token).then(setNotifications).finally(() => setLoading(false));
  }, [token]);

  const markRead = async (id: string) => {
    if (!token) return;
    await deadlinesAPI.markRead(id, token).catch(() => {});
    setNotifications(prev => prev.map(n => n.id === id ? { ...n, is_read: true } : n));
  };

  const unread = notifications.filter(n => !n.is_read).length;

  return (
    <div>
      <div style={{ marginBottom: '28px', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div>
          <h1 style={{ fontSize: '24px', fontWeight: 800 }}>Notifications</h1>
          <p style={{ color: 'var(--text-secondary)', fontSize: '13px', marginTop: '4px' }}>
            {unread > 0 ? `${unread} unread notification${unread > 1 ? 's' : ''}` : 'All caught up!'}
          </p>
        </div>
        {unread > 0 && (
          <div style={{
            background: 'var(--accent-primary)', color: 'white',
            borderRadius: '99px', padding: '4px 12px', fontSize: '13px', fontWeight: 700,
          }}>{unread}</div>
        )}
      </div>

      {loading && <p style={{ color: 'var(--text-muted)' }}>⏳ Loading...</p>}

      {!loading && notifications.length === 0 && (
        <div className="card" style={{ textAlign: 'center', padding: '48px' }}>
          <div style={{ fontSize: '48px', marginBottom: '16px' }}>🔔</div>
          <p style={{ color: 'var(--text-secondary)' }}>No notifications yet.</p>
        </div>
      )}

      <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
        {notifications.map(n => (
          <div key={n.id} className="card" style={{
            borderLeft: `3px solid ${n.is_read ? 'var(--border)' : 'var(--accent-primary)'}`,
            opacity: n.is_read ? 0.7 : 1,
          }}>
            <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: '16px' }}>
              <div style={{ flex: 1 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
                  <span style={{ fontSize: '16px' }}>📅</span>
                  <div style={{ fontSize: '14px', fontWeight: 600, color: 'var(--text-primary)' }}>{n.title}</div>
                  {!n.is_read && (
                    <div style={{
                      background: 'var(--accent-primary)', color: 'white',
                      borderRadius: '99px', padding: '1px 8px', fontSize: '10px', fontWeight: 700,
                    }}>NEW</div>
                  )}
                </div>
                <div style={{ fontSize: '13px', color: 'var(--text-secondary)', lineHeight: 1.6, whiteSpace: 'pre-line' }}>
                  {n.message}
                </div>
                <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '8px' }}>
                  {new Date(n.sent_at).toLocaleString()}
                </div>
              </div>
              {!n.is_read && (
                <button className="btn btn-secondary btn-sm" onClick={() => markRead(n.id)}>
                  Mark read
                </button>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
