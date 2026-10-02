'use client';

import { useState, useRef } from 'react';
import { useAuth } from '@/hooks/useAuth';
import { analysisAPI, deadlinesAPI } from '@/lib/api';

type AnalysisMode = 'missing' | 'responses' | 'compare';

export default function AnalysisPage() {
  const { token, user } = useAuth();
  const [mode, setMode] = useState<AnalysisMode>('responses');
  const [masterFile, setMasterFile] = useState<File | null>(null);
  const [responseFile, setResponseFile] = useState<File | null>(null);
  const [masterCol, setMasterCol] = useState('Name');
  const [responseCol, setResponseCol] = useState('Name');
  const [responseValCol, setResponseValCol] = useState('Response');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [showDeadline, setShowDeadline] = useState(false);
  const [deadlineDate, setDeadlineDate] = useState('');
  const [deadlineTime, setDeadlineTime] = useState('');
  const [deadlineTitle, setDeadlineTitle] = useState('');
  const [deadlineLoading, setDeadlineLoading] = useState(false);
  const [deadlineSuccess, setDeadlineSuccess] = useState(false);

  const analyze = async () => {
    if (!token || !masterFile || !responseFile) return;
    setLoading(true);
    setResult(null);

    const formData = new FormData();
    formData.append('master_file', masterFile);
    formData.append('response_file', responseFile);
    formData.append('master_name_col', masterCol);
    formData.append('response_name_col', responseCol);

    try {
      let res;
      if (mode === 'missing') {
        res = await analysisAPI.detectMissing(formData, token);
      } else if (mode === 'responses') {
        formData.append('response_col', responseValCol);
        res = await analysisAPI.analyzeResponses(formData, token);
      } else {
        formData.append('col_a', masterCol);
        formData.append('col_b', responseCol);
        res = await analysisAPI.compareLists(formData, token);
      }
      setResult(res);
    } catch (err: any) {
      setResult({ error: err.message });
    } finally {
      setLoading(false);
    }
  };

  const createDeadline = async () => {
    if (!token || !deadlineDate || !deadlineTime) return;
    setDeadlineLoading(true);
    try {
      await deadlinesAPI.create({
        title: deadlineTitle || 'Response Deadline',
        deadline_date: deadlineDate,
        deadline_time: deadlineTime,
        missing_count: result?.missing_count || result?.no_response_count,
        missing_names: result?.missing_names || result?.no_response_students || [],
      }, token);
      setDeadlineSuccess(true);
      setShowDeadline(false);
    } catch (err: any) {
      alert('Failed to create deadline: ' + err.message);
    } finally {
      setDeadlineLoading(false);
    }
  };

  return (
    <div>
      <div style={{ marginBottom: '28px' }}>
        <h1 style={{ fontSize: '24px', fontWeight: 800 }}>Multi-Document Analysis</h1>
        <p style={{ color: 'var(--text-secondary)', fontSize: '13px', marginTop: '4px' }}>
          Deterministic counting, matching, and comparison — exact results, no LLM estimation
        </p>
      </div>

      {/* Mode selector */}
      <div style={{ display: 'flex', gap: '8px', marginBottom: '24px', flexWrap: 'wrap' }}>
        {[
          { id: 'responses', label: '📊 Yes/No Analysis', desc: 'Count Yes, No, and Missing responses' },
          { id: 'missing', label: '👤 Missing Responses', desc: 'Find who hasn\'t responded' },
          { id: 'compare', label: '🔍 Compare Lists', desc: 'Find differences between two lists' },
        ].map(m => (
          <button
            key={m.id}
            className={`btn ${mode === m.id ? 'btn-primary' : 'btn-secondary'}`}
            onClick={() => { setMode(m.id as AnalysisMode); setResult(null); }}
          >
            {m.label}
          </button>
        ))}
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '24px', alignItems: 'start' }}>
        {/* Input */}
        <div className="card">
          <h2 className="card-title" style={{ marginBottom: '20px' }}>
            {mode === 'responses' ? 'Upload Documents' : mode === 'missing' ? 'Upload Files' : 'Upload Lists'}
          </h2>

          {[
            { label: 'Master Student List', setter: setMasterFile, file: masterFile },
            { label: mode === 'compare' ? 'List B' : 'Form Responses / Data', setter: setResponseFile, file: responseFile },
          ].map(({ label, setter, file }) => (
            <div className="form-group" key={label}>
              <label className="form-label">{label} (CSV or Excel)</label>
              <div
                style={{
                  padding: '16px', border: `2px dashed ${file ? 'var(--accent-green)' : 'var(--border)'}`,
                  borderRadius: '8px', cursor: 'pointer', textAlign: 'center',
                  background: file ? 'rgba(16,185,129,0.05)' : 'var(--bg-input)',
                  transition: 'all 0.2s',
                }}
                onClick={() => {
                  const inp = document.createElement('input');
                  inp.type = 'file'; inp.accept = '.csv,.xlsx,.xls';
                  inp.onchange = (e) => setter((e.target as HTMLInputElement).files?.[0] || null);
                  inp.click();
                }}
              >
                {file ? (
                  <><span style={{ color: 'var(--accent-green)' }}>✅ {file.name}</span></>
                ) : (
                  <><span>📂</span> <span style={{ color: 'var(--text-muted)', fontSize: '13px' }}>Click to select CSV / Excel</span></>
                )}
              </div>
            </div>
          ))}

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
            <div className="form-group">
              <label className="form-label">Name Column (Master)</label>
              <input className="form-input" value={masterCol} onChange={e => setMasterCol(e.target.value)} />
            </div>
            <div className="form-group">
              <label className="form-label">Name Column (Response)</label>
              <input className="form-input" value={responseCol} onChange={e => setResponseCol(e.target.value)} />
            </div>
          </div>

          {mode === 'responses' && (
            <div className="form-group">
              <label className="form-label">Response Column</label>
              <input className="form-input" value={responseValCol} onChange={e => setResponseValCol(e.target.value)} />
            </div>
          )}

          <button
            className="btn btn-primary"
            style={{ width: '100%', justifyContent: 'center' }}
            onClick={analyze}
            disabled={!masterFile || !responseFile || loading}
          >
            {loading ? '⏳ Analyzing...' : '🔍 Analyze'}
          </button>
        </div>

        {/* Results */}
        <div>
          {result?.error && (
            <div className="card" style={{ borderColor: 'rgba(239,68,68,0.3)' }}>
              <p style={{ color: 'var(--accent-red)' }}>❌ {result.error}</p>
            </div>
          )}

          {result && !result.error && mode === 'responses' && (
            <div className="card">
              <h2 className="card-title">Analysis Results</h2>
              <div className="stats-grid" style={{ gridTemplateColumns: 'repeat(2, 1fr)', marginBottom: '16px' }}>
                {[
                  { label: 'Total', value: result.total_students, color: 'var(--accent-primary)' },
                  { label: 'Yes ✅', value: result.yes_count, color: 'var(--accent-green)' },
                  { label: 'No ❌', value: result.no_count, color: 'var(--accent-red)' },
                  { label: 'No Response 📭', value: result.no_response_count, color: 'var(--accent-amber)' },
                ].map(s => (
                  <div key={s.label} style={{ padding: '16px', background: 'var(--bg-input)', borderRadius: '10px', border: '1px solid var(--border)' }}>
                    <div style={{ fontSize: '28px', fontWeight: 800, color: s.color }}>{s.value}</div>
                    <div style={{ fontSize: '12px', color: 'var(--text-secondary)', marginTop: '4px' }}>{s.label}</div>
                  </div>
                ))}
              </div>

              {result.no_response_students?.length > 0 && (
                <>
                  <div style={{ fontSize: '13px', fontWeight: 600, marginBottom: '10px', color: 'var(--accent-amber)' }}>
                    📭 Pending responses ({result.no_response_students.length})
                  </div>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px', marginBottom: '16px' }}>
                    {result.no_response_students.map((n: string) => (
                      <span key={n} style={{
                        padding: '4px 10px', background: 'rgba(245,158,11,0.1)',
                        borderRadius: '99px', fontSize: '12px', color: 'var(--accent-amber)',
                        border: '1px solid rgba(245,158,11,0.25)',
                      }}>{n}</span>
                    ))}
                  </div>
                  {user?.role !== 'STUDENT' && (
                    <button className="btn btn-secondary" onClick={() => setShowDeadline(true)}>
                      📅 Set Deadline for Pending Students
                    </button>
                  )}
                  {deadlineSuccess && (
                    <div style={{ marginTop: '10px', color: 'var(--accent-green)', fontSize: '13px' }}>
                      ✅ Deadline created and scheduler activated.
                    </div>
                  )}
                </>
              )}
            </div>
          )}

          {result && !result.error && mode === 'missing' && (
            <div className="card">
              <h2 className="card-title">Missing Responses</h2>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '12px', marginBottom: '16px' }}>
                {[
                  { label: 'Total', value: result.total },
                  { label: 'Responded', value: result.responded, color: 'var(--accent-green)' },
                  { label: 'Missing', value: result.missing_count, color: 'var(--accent-red)' },
                ].map(s => (
                  <div key={s.label} style={{ padding: '14px', background: 'var(--bg-input)', borderRadius: '10px', border: '1px solid var(--border)', textAlign: 'center' }}>
                    <div style={{ fontSize: '24px', fontWeight: 800, color: s.color || 'var(--text-primary)' }}>{s.value}</div>
                    <div style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>{s.label}</div>
                  </div>
                ))}
              </div>
              {result.missing_names?.map((n: string) => (
                <span key={n} style={{ display: 'inline-block', padding: '4px 10px', margin: '3px', background: 'rgba(239,68,68,0.1)', borderRadius: '99px', fontSize: '12px', color: 'var(--accent-red)' }}>{n}</span>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Deadline Modal */}
      {showDeadline && (
        <div className="modal-overlay">
          <div className="modal-card">
            <div className="modal-icon">📅</div>
            <h2 className="modal-title">Set Deadline</h2>
            <p className="modal-body">
              {result?.no_response_count || result?.missing_count} student(s) have not responded.
              Set a deadline to trigger a faculty notification.
            </p>
            <div className="form-group">
              <label className="form-label">Deadline Title</label>
              <input className="form-input" value={deadlineTitle} onChange={e => setDeadlineTitle(e.target.value)} placeholder="Form Response Deadline" />
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
              <div className="form-group">
                <label className="form-label">Date</label>
                <input className="form-input" type="date" value={deadlineDate} onChange={e => setDeadlineDate(e.target.value)} />
              </div>
              <div className="form-group">
                <label className="form-label">Time</label>
                <input className="form-input" type="time" value={deadlineTime} onChange={e => setDeadlineTime(e.target.value)} />
              </div>
            </div>
            <div className="modal-actions">
              <button className="btn btn-primary btn-lg" style={{ justifyContent: 'center' }} onClick={createDeadline} disabled={deadlineLoading || !deadlineDate || !deadlineTime}>
                {deadlineLoading ? '⏳ Creating...' : '📅 Confirm Deadline'}
              </button>
              <button className="btn btn-secondary" style={{ justifyContent: 'center' }} onClick={() => setShowDeadline(false)}>Cancel</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
