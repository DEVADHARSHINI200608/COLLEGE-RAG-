'use client';

import { useState, useRef } from 'react';
import { useAuth } from '@/hooks/useAuth';
import { documentsAPI } from '@/lib/api';

const ACCEPTED_TYPES = '.pdf,.doc,.docx,.ppt,.pptx,.txt,.md,.csv,.xlsx';

export default function DocumentsPage() {
  const { user, token } = useAuth();
  const [files, setFiles] = useState<File[]>([]);
  const [sourceName, setSourceName] = useState('');
  const [classification, setClassification] = useState('NON_CONFIDENTIAL');
  const [isStandard, setIsStandard] = useState(false);
  const [department, setDepartment] = useState('');
  const [uploading, setUploading] = useState(false);
  const [results, setResults] = useState<any[]>([]);
  const [dragging, setDragging] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragging(false);
    const dropped = Array.from(e.dataTransfer.files);
    setFiles(prev => [...prev, ...dropped]);
  };

  const handleUpload = async () => {
    if (!token || !files.length) return;
    setUploading(true);
    setResults([]);

    const formData = new FormData();
    files.forEach(f => formData.append('files', f));
    formData.append('source_name', sourceName || files[0].name);
    formData.append('classification', classification);
    formData.append('is_standard_resource', String(isStandard));
    if (department) formData.append('department', department);

    try {
      const res = await documentsAPI.upload(formData, token);
      setResults(res.results);
      setFiles([]);
      setSourceName('');
    } catch (err: any) {
      setResults([{ filename: 'Upload', status: 'error', message: err.message }]);
    } finally {
      setUploading(false);
    }
  };

  const canUploadConfidential = user?.role === 'FACULTY' || user?.role === 'ADMIN';
  const canMarkStandard = user?.role === 'FACULTY' || user?.role === 'ADMIN';

  return (
    <div>
      <div style={{ marginBottom: '28px' }}>
        <h1 style={{ fontSize: '24px', fontWeight: 800, letterSpacing: '-0.02em' }}>Upload Documents</h1>
        <p style={{ color: 'var(--text-secondary)', fontSize: '13px', marginTop: '4px' }}>
          Supported: PDF, DOCX, PPTX, TXT, CSV, XLSX, Markdown
        </p>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 340px', gap: '24px', alignItems: 'start' }}>
        {/* Upload Zone */}
        <div className="card">
          <div
            className={`upload-zone ${dragging ? 'dragging' : ''}`}
            onDragOver={e => { e.preventDefault(); setDragging(true); }}
            onDragLeave={() => setDragging(false)}
            onDrop={handleDrop}
            onClick={() => fileRef.current?.click()}
          >
            <div className="upload-icon">📤</div>
            <div className="upload-title">Drop files here or click to browse</div>
            <div className="upload-subtitle" style={{ marginTop: '6px' }}>
              PDF • DOCX • PPTX • TXT • CSV • XLSX • Markdown
            </div>
            <div className="upload-subtitle" style={{ marginTop: '4px' }}>
              Max {50}MB per file
            </div>
            <input ref={fileRef} type="file" multiple accept={ACCEPTED_TYPES} style={{ display: 'none' }}
              onChange={e => setFiles(prev => [...prev, ...Array.from(e.target.files || [])])} />
          </div>

          {/* Selected files */}
          {files.length > 0 && (
            <div style={{ marginTop: '20px' }}>
              <div style={{ fontSize: '13px', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '10px' }}>
                {files.length} file(s) selected
              </div>
              {files.map((f, i) => (
                <div key={i} style={{
                  display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                  padding: '10px 14px', background: 'var(--bg-input)',
                  borderRadius: '8px', marginBottom: '6px', border: '1px solid var(--border)',
                }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                    <span>📄</span>
                    <div>
                      <div style={{ fontSize: '13px', fontWeight: 500 }}>{f.name}</div>
                      <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                        {(f.size / 1024).toFixed(1)} KB
                      </div>
                    </div>
                  </div>
                  <button
                    className="btn btn-danger btn-sm"
                    onClick={(e) => { e.stopPropagation(); setFiles(prev => prev.filter((_, j) => j !== i)); }}
                  >✕</button>
                </div>
              ))}
            </div>
          )}

          {/* Results */}
          {results.length > 0 && (
            <div style={{ marginTop: '20px' }}>
              {results.map((r, i) => (
                <div key={i} style={{
                  padding: '12px 14px', borderRadius: '8px', marginBottom: '6px',
                  background: r.status === 'success' ? 'rgba(16,185,129,0.1)' : 'rgba(239,68,68,0.1)',
                  border: `1px solid ${r.status === 'success' ? 'rgba(16,185,129,0.25)' : 'rgba(239,68,68,0.25)'}`,
                }}>
                  <div style={{ fontSize: '13px', fontWeight: 600, color: r.status === 'success' ? 'var(--accent-green)' : 'var(--accent-red)' }}>
                    {r.status === 'success' ? '✅' : '❌'} {r.filename}
                  </div>
                  {r.status === 'success' && (
                    <div style={{ fontSize: '12px', color: 'var(--text-secondary)', marginTop: '4px' }}>
                      {r.chunks} chunks indexed • ID: {r.source_id?.slice(0,8)}...
                    </div>
                  )}
                  {r.message && (
                    <div style={{ fontSize: '12px', color: 'var(--text-muted)', marginTop: '4px' }}>{r.message}</div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Settings Panel */}
        <div className="card">
          <h2 className="card-title" style={{ marginBottom: '20px' }}>Document Settings</h2>

          <div className="form-group">
            <label className="form-label">Source Name</label>
            <input className="form-input" value={sourceName} onChange={e => setSourceName(e.target.value)}
              placeholder="e.g., ML Notes Chapter 3" />
          </div>

          <div className="form-group">
            <label className="form-label">Classification</label>
            <div className="classification-toggle">
              <button
                className={`classification-option ${classification === 'NON_CONFIDENTIAL' ? 'active-non-confidential' : ''}`}
                onClick={() => setClassification('NON_CONFIDENTIAL')}
              >🌐 Non-Confidential</button>
              <button
                className={`classification-option ${classification === 'CONFIDENTIAL' ? 'active-confidential' : ''}`}
                onClick={() => { if (canUploadConfidential) setClassification('CONFIDENTIAL'); }}
                disabled={!canUploadConfidential}
                style={{ opacity: canUploadConfidential ? 1 : 0.4 }}
              >🔒 Confidential</button>
            </div>
            {!canUploadConfidential && (
              <p style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '6px' }}>
                Confidential upload requires Faculty/Admin role
              </p>
            )}
          </div>

          {canMarkStandard && (
            <div className="form-group">
              <label style={{ display: 'flex', alignItems: 'center', gap: '10px', cursor: 'pointer' }}>
                <input type="checkbox" checked={isStandard} onChange={e => setIsStandard(e.target.checked)}
                  style={{ width: '16px', height: '16px', accentColor: 'var(--accent-primary)' }} />
                <div>
                  <div className="form-label" style={{ marginBottom: 0 }}>Mark as Standard Resource</div>
                  <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                    Higher priority for student queries
                  </div>
                </div>
              </label>
            </div>
          )}

          <div className="form-group">
            <label className="form-label">Department (optional)</label>
            <input className="form-input" value={department} onChange={e => setDepartment(e.target.value)}
              placeholder="e.g., Computer Science" />
          </div>

          <button
            className="btn btn-primary"
            style={{ width: '100%', justifyContent: 'center' }}
            onClick={handleUpload}
            disabled={!files.length || uploading}
          >
            {uploading ? '⏳ Uploading & Indexing...' : `📤 Upload ${files.length ? `${files.length} file(s)` : ''}`}
          </button>

          {classification === 'CONFIDENTIAL' && (
            <div style={{
              marginTop: '12px', padding: '10px 12px', borderRadius: '8px',
              background: 'var(--confidential-bg)', border: '1px solid rgba(239,68,68,0.2)',
            }}>
              <p style={{ fontSize: '11px', color: 'var(--confidential)' }}>
                🔒 This document will be stored in the confidential domain with restricted access.
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
