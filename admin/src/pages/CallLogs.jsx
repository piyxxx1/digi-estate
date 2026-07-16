import React, { useState } from 'react';
import { useAdmin } from '../context/AdminContext';
import { History, Eye, Search, AlertCircle, PhoneIncoming, MessageSquare, Clock } from 'lucide-react';

const CallLogs = () => {
  const { calls, isLoadingCalls } = useAdmin();
  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState('All');
  const [selectedCall, setSelectedCall] = useState(null);

  // Auto-select first call when loaded
  React.useEffect(() => {
    if (calls.length > 0 && !selectedCall) {
      setSelectedCall(calls[0]);
    }
  }, [calls, selectedCall]);

  const filteredCalls = calls.filter(call => {
    const matchesSearch = call.caller_name.toLowerCase().includes(searchTerm.toLowerCase()) || 
                          call.phone_number.includes(searchTerm) ||
                          (call.transcript && call.transcript.toLowerCase().includes(searchTerm.toLowerCase()));
    const matchesStatus = statusFilter === 'All' || call.status === statusFilter;
    return matchesSearch && matchesStatus;
  });

  const getStatusColor = (status) => {
    switch (status) {
      case 'Completed': return 'var(--success)';
      case 'Failed': return 'var(--danger)';
      case 'In Progress': return 'var(--warning)';
      default: return 'var(--text-muted)';
    }
  };

  return (
    <div className="page-content">
      <div className="logs-grid">
        
        {/* Left Side: Call List */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
          <div className="search-filter-bar">
            <div className="search-input-wrapper">
              <Search size={16} />
              <input 
                type="text" 
                className="input-field" 
                placeholder="Search transcripts or callers..." 
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
              />
            </div>

            <select 
              className="select-field"
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
            >
              <option value="All">All Statuses</option>
              <option value="Completed">Completed</option>
              <option value="In Progress">In Progress</option>
              <option value="Failed">Failed</option>
            </select>
          </div>

          <div className="glass-card" style={{ flex: 1, maxHeight: '680px', overflowY: 'auto', padding: '1rem' }}>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
              {isLoadingCalls ? (
                <div style={{ textAlign: 'center', padding: '3rem', color: 'var(--zoho-blue)' }}>
                  <div className="status-dot pulsing" style={{ backgroundColor: 'var(--zoho-blue)', width: '12px', height: '12px', display: 'inline-block', marginBottom: '1rem' }}></div>
                  <p>Syncing call logs from Exotel...</p>
                </div>
              ) : filteredCalls.length === 0 ? (
                <div style={{ textAlign: 'center', padding: '3rem', color: 'var(--text-muted)' }}>
                  <AlertCircle size={32} style={{ marginBottom: '0.5rem', opacity: 0.5 }} />
                  <p>No call logs match the criteria.</p>
                </div>
              ) : (
                filteredCalls.map(call => (
                  <div 
                    key={call.id}
                    className="agent-mini-card"
                    style={{ 
                      cursor: 'pointer',
                      borderLeft: `4px solid ${getStatusColor(call.status)}`,
                      background: selectedCall?.id === call.id ? 'var(--zoho-blue-light)' : '',
                      borderColor: selectedCall?.id === call.id ? 'var(--zoho-blue)' : ''
                    }}
                    onClick={() => setSelectedCall(call)}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                      <div>
                        <span style={{ fontWeight: 600, fontSize: '0.9rem', color: 'var(--text-primary)' }}>{call.caller_name}</span>
                        <span style={{ display: 'block', fontSize: '0.75rem', color: 'var(--text-muted)' }}>{call.phone_number}</span>
                      </div>
                      <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                        {new Date(call.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                      </span>
                    </div>

                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '0.75rem', color: 'var(--text-secondary)', marginTop: '0.5rem' }}>
                      <span>Duration: <strong>{call.status === 'In Progress' ? 'Active' : `${call.call_duration}s`}</strong></span>
                      <span style={{ color: 'var(--zoho-teal)' }}>{call.latency.total}</span>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>

        {/* Right Side: Conversation Auditor Console */}
        <div className="log-detail-panel">
          {selectedCall ? (
            <div className="glass-card" style={{ height: '100%', display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
              <div style={{ borderBottom: '1px solid var(--border-color)', paddingBottom: '1rem' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <h3 style={{ fontFamily: 'var(--font-display)', fontSize: '1.25rem', fontWeight: 600 }}>Call Audit Logs</h3>
                  <span className={`badge`} style={{ 
                    background: selectedCall.status === 'Completed' ? 'var(--zoho-green-light)' : selectedCall.status === 'Failed' ? 'var(--zoho-red-light)' : 'var(--zoho-orange-light)', 
                    color: getStatusColor(selectedCall.status),
                    border: `1px solid ${getStatusColor(selectedCall.status)}40`,
                    textTransform: 'none'
                  }}>
                    {selectedCall.status}
                  </span>
                </div>
                
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem', marginTop: '1rem', fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
                  <div>ID: <strong style={{ color: 'var(--text-primary)' }}>{selectedCall.id}</strong></div>
                  <div>Timestamp: <strong style={{ color: 'var(--text-primary)' }}>{new Date(selectedCall.created_at).toLocaleString()}</strong></div>
                  <div>Target Caller: <strong style={{ color: 'var(--text-primary)' }}>{selectedCall.caller_name}</strong></div>
                  <div>Phone: <strong style={{ color: 'var(--text-primary)' }}>{selectedCall.phone_number}</strong></div>
                </div>
              </div>

              {/* Latency Pipeline Audit */}
              <div>
                <span style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-secondary)', display: 'flex', alignItems: 'center', gap: '0.35rem', marginBottom: '0.5rem' }}>
                  <Clock size={14} style={{ color: 'var(--zoho-teal)' }} />
                  Latency Pipeline Breakdowns
                </span>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '0.5rem' }}>
                  <div className="latency-item">
                    <span style={{ color: 'var(--text-muted)', fontSize: '0.7rem' }}>STT Decode</span>
                    <span className="latency-val">{selectedCall.latency.stt}</span>
                  </div>
                  <div className="latency-item">
                    <span style={{ color: 'var(--text-muted)', fontSize: '0.7rem' }}>LLM Think</span>
                    <span className="latency-val" style={{ color: 'var(--zoho-blue)' }}>{selectedCall.latency.llm}</span>
                  </div>
                  <div className="latency-item">
                    <span style={{ color: 'var(--text-muted)', fontSize: '0.7rem' }}>TTS Render</span>
                    <span className="latency-val">{selectedCall.latency.tts}</span>
                  </div>
                  <div className="latency-item" style={{ background: 'var(--zoho-teal-light)', borderColor: 'rgba(0, 188, 212, 0.15)' }}>
                    <span style={{ color: 'var(--text-secondary)', fontSize: '0.7rem', fontWeight: 600 }}>Total RT</span>
                    <span className="latency-val" style={{ color: 'var(--text-primary)' }}>{selectedCall.latency.total}</span>
                  </div>
                </div>
              </div>

              {/* Transcript dialogue box */}
              <div style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
                <span style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-secondary)', display: 'flex', alignItems: 'center', gap: '0.35rem', marginBottom: '0.5rem' }}>
                  <MessageSquare size={14} style={{ color: 'var(--zoho-blue)' }} />
                  Audio Stream Transcript Log
                </span>
                <div className="transcript-bubble" style={{ flex: 1, maxHeight: '350px' }}>
                  {selectedCall.transcript}
                </div>
              </div>

              {/* AI Action/Result summary */}
              <div style={{ background: 'var(--zoho-teal-light)', border: '1px solid rgba(0, 188, 212, 0.15)', padding: '0.75rem 1rem', borderRadius: '10px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.8rem', fontWeight: 600, color: 'var(--zoho-teal)', marginBottom: '0.25rem' }}>
                  <PhoneIncoming size={12} />
                  <span>Pipeline Resolution Decision:</span>
                </div>
                <p style={{ fontSize: '0.8rem', color: 'var(--text-primary)', fontStyle: 'italic' }}>
                  "{selectedCall.ai_response}"
                </p>
              </div>

            </div>
          ) : (
            <div className="glass-card" style={{ height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--text-muted)' }}>
              Select a call session on the left to view transcription logs.
            </div>
          )}
        </div>

      </div>
    </div>
  );
};

export default CallLogs;
