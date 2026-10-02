'use client';

import { useState, useRef, useEffect } from 'react';
import { useAuth } from '@/hooks/useAuth';
import { chatAPI } from '@/lib/api';

interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  sources?: any[];
  model_used?: string;
  is_local?: boolean;
  loading?: boolean;
}

interface FallbackState {
  show: boolean;
  reason: string;
  pendingQuery: string;
  sessionId: string | null;
}

export default function ChatPage() {
  const { user, token } = useAuth();
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [modelMode, setModelMode] = useState<'EXTERNAL' | 'LOCAL'>('EXTERNAL');
  const [sending, setSending] = useState(false);
  const [fallback, setFallback] = useState<FallbackState>({ show: false, reason: '', pendingQuery: '', sessionId: null });
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  useEffect(() => {
    if (token) {
      chatAPI.modelStatus(token).then(s => setModelMode(s.is_local ? 'LOCAL' : 'EXTERNAL')).catch(() => {});
    }
  }, [token]);

  const sendQuery = async (query: string, forceLocal = false, sid?: string | null) => {
    if (!token || !query.trim()) return;

    const userMsg: Message = { id: Date.now().toString(), role: 'user', content: query };
    const loadingMsg: Message = { id: 'loading', role: 'assistant', content: '', loading: true };

    setMessages(prev => [...prev, userMsg, loadingMsg]);
    setSending(true);

    try {
      const res = await chatAPI.query({
        query,
        session_id: sid ?? sessionId ?? undefined,
        force_local_model: forceLocal,
      }, token);

      setSessionId(res.session_id);

      // Handle fallback confirmation required
      if (res.needs_fallback_confirmation && !forceLocal) {
        setMessages(prev => prev.filter(m => m.id !== 'loading'));
        setFallback({ show: true, reason: res.fallback_reason || 'External AI unavailable', pendingQuery: query, sessionId: res.session_id });
        setSending(false);
        return;
      }

      // Success
      const assistantMsg: Message = {
        id: res.message_id,
        role: 'assistant',
        content: res.answer || 'No response generated.',
        sources: res.sources,
        model_used: res.model_used || undefined,
        is_local: res.is_local_model,
      };

      setMessages(prev => [...prev.filter(m => m.id !== 'loading'), assistantMsg]);
      setModelMode(res.is_local_model ? 'LOCAL' : 'EXTERNAL');
    } catch (err: any) {
      setMessages(prev => [
        ...prev.filter(m => m.id !== 'loading'),
        { id: Date.now().toString(), role: 'assistant', content: `❌ Error: ${err.message}` },
      ]);
    } finally {
      setSending(false);
    }
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || sending) return;
    sendQuery(input.trim());
    setInput('');
  };

  const confirmLocalModel = () => {
    setFallback(prev => ({ ...prev, show: false }));
    sendQuery(fallback.pendingQuery, true, fallback.sessionId);
  };

  return (
    <div>
      {/* Header */}
      <div style={{ marginBottom: '20px' }}>
        <h1 style={{ fontSize: '24px', fontWeight: 800, letterSpacing: '-0.02em' }}>Ask AI</h1>
        <p style={{ color: 'var(--text-secondary)', fontSize: '13px', marginTop: '4px' }}>
          Intelligent RAG — retrieves from your documents, standard resources, and approved web sources
        </p>
      </div>

      {/* AI Mode Banner */}
      <div className={`ai-mode-banner ${modelMode === 'LOCAL' ? 'ai-mode-local' : 'ai-mode-external'}`}>
        <span className="ai-mode-dot" />
        AI Mode: <strong>{modelMode === 'LOCAL' ? 'Local Model' : 'External AI'}</strong>
        <span style={{ marginLeft: 'auto', fontSize: '11px', opacity: 0.7 }}>
          {modelMode === 'LOCAL' ? 'Using locally hosted model' : 'Connected to cloud AI'}
        </span>
      </div>

      {/* Chat Container */}
      <div className="chat-container">
        <div className="chat-messages">
          {messages.length === 0 && (
            <div style={{ textAlign: 'center', padding: '40px 20px', color: 'var(--text-muted)' }}>
              <div style={{ fontSize: '48px', marginBottom: '16px' }}>🤖</div>
              <p style={{ fontSize: '15px', fontWeight: 500, marginBottom: '8px', color: 'var(--text-secondary)' }}>
                Ask anything about your documents
              </p>
              <p style={{ fontSize: '13px' }}>
                I'll search your uploaded materials, standard resources, and approved web sources.
              </p>
              <div style={{ marginTop: '20px', display: 'flex', gap: '8px', flexWrap: 'wrap', justifyContent: 'center' }}>
                {[
                  'Explain the key concepts from my notes',
                  'Who has not responded to the form?',
                  'Summarize the course material',
                ].map(s => (
                  <button
                    key={s}
                    className="btn btn-secondary btn-sm"
                    onClick={() => { setInput(s); }}
                  >
                    {s}
                  </button>
                ))}
              </div>
            </div>
          )}

          {messages.map(msg => (
            <div key={msg.id} className={`message-bubble ${msg.role}`}>
              <div className="message-avatar">
                {msg.role === 'user' ? (user?.full_name?.[0] || '?') : '🤖'}
              </div>
              <div style={{ maxWidth: '100%' }}>
                <div className="message-content">
                  {msg.loading ? (
                    <div style={{ display: 'flex', gap: '6px', alignItems: 'center' }}>
                      {[0, 1, 2].map(i => (
                        <div key={i} style={{
                          width: '8px', height: '8px', borderRadius: '50%',
                          background: 'var(--accent-primary)',
                          animation: `pulse 1.2s ease-in-out ${i * 0.2}s infinite`,
                        }} />
                      ))}
                    </div>
                  ) : (
                    <div style={{ whiteSpace: 'pre-wrap' }}>{msg.content}</div>
                  )}
                </div>

                {/* Sources */}
                {msg.sources && msg.sources.length > 0 && (
                  <div className="message-sources" style={{ marginTop: '8px' }}>
                    <div className="message-sources-label">Sources used</div>
                    <div>
                      {msg.sources.map((src, i) => (
                        <span key={i} className="source-chip">
                          {src.classification === 'CONFIDENTIAL' ? '🔒' : '📄'} {src.source_name || src.url || 'Unknown'}
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                {/* Model info */}
                {msg.model_used && (
                  <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '6px', marginLeft: '4px' }}>
                    {msg.is_local ? '🏠' : '☁️'} {msg.model_used}
                  </div>
                )}
              </div>
            </div>
          ))}
          <div ref={messagesEndRef} />
        </div>

        {/* Input area */}
        <div className="chat-input-area">
          <textarea
            className="chat-input"
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={e => {
              if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSubmit(e); }
            }}
            placeholder="Ask about your documents, student responses, course material..."
            rows={1}
            disabled={sending}
          />
          <button
            className="btn btn-primary"
            onClick={handleSubmit}
            disabled={!input.trim() || sending}
            style={{ minWidth: '80px', justifyContent: 'center' }}
          >
            {sending ? '⏳' : '↑ Send'}
          </button>
        </div>
      </div>

      {/* Fallback Confirmation Modal */}
      {fallback.show && (
        <div className="modal-overlay">
          <div className="modal-card">
            <div className="modal-icon">⚡</div>
            <h2 className="modal-title">External AI Limit Reached</h2>
            <p className="modal-body">
              The external AI service has reached its configured usage limit for today.
              <br /><br />
              <strong style={{ color: 'var(--accent-amber)' }}>Reason:</strong> {fallback.reason}
              <br /><br />
              You can continue using the system with the <strong>local AI model</strong> until the external service becomes available again.
            </p>
            <div className="modal-actions">
              <button
                className="btn btn-primary btn-lg"
                style={{ justifyContent: 'center', background: 'linear-gradient(135deg, var(--accent-amber), #d97706)' }}
                onClick={confirmLocalModel}
              >
                🏠 Continue with Local Model
              </button>
              <button
                className="btn btn-secondary"
                style={{ justifyContent: 'center' }}
                onClick={() => setFallback(prev => ({ ...prev, show: false }))}
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
