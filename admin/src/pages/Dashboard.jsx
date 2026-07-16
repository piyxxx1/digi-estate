import React, { useState } from 'react';
import { useAdmin } from '../context/AdminContext';
import { 
  PhoneCall, 
  Activity, 
  Clock, 
  CheckCircle, 
  Play, 
  Eye, 
  ChevronRight, 
  CornerDownRight, 
  AlertTriangle,
  History
} from 'lucide-react';

const Dashboard = () => {
  const { metrics, calls, leads, triggerCall } = useAdmin();
  const [selectedCall, setSelectedCall] = useState(null);

  // Get some active leads to display quick trigger buttons
  const pendingLeads = leads.filter(l => l.status === 'Pending').slice(0, 3);

  const getStatusBadgeClass = (status) => {
    switch (status) {
      case 'Completed': return 'badge-success';
      case 'In Progress': return 'badge-warning';
      case 'Failed': return 'badge-danger';
      default: return 'badge-secondary';
    }
  };

  return (
    <div className="page-content">
      {/* Metrics Section */}
      <div className="metrics-row">
        {/* Total Calls */}
        <div className="glass-card stat-card" style={{ '--accent-gradient': 'var(--zoho-blue)' }}>
          <div className="stat-info">
            <span className="stat-label">Total Outbound Calls</span>
            <span className="stat-value">{metrics.totalCalls}</span>
            <span className="stat-change up">↑ +14.2% today</span>
          </div>
          <div className="stat-icon-box" style={{ '--icon-color': 'var(--zoho-blue)' }}>
            <PhoneCall size={20} />
          </div>
        </div>

        {/* Avg Latency */}
        <div className="glass-card stat-card" style={{ '--accent-gradient': 'var(--zoho-teal)' }}>
          <div className="stat-info">
            <span className="stat-label">Avg Telephony Latency</span>
            <span className="stat-value">{metrics.avgLatency}</span>
            <span className="stat-change down" style={{ color: 'var(--zoho-green)' }}>↓ -80ms improvement</span>
          </div>
          <div className="stat-icon-box" style={{ '--icon-color': 'var(--zoho-teal)' }}>
            <Clock size={20} />
          </div>
        </div>

        {/* Success Rate */}
        <div className="glass-card stat-card" style={{ '--accent-gradient': 'var(--zoho-green)' }}>
          <div className="stat-info">
            <span className="stat-label">Intent Success Rate</span>
            <span className="stat-value">{metrics.successRate}</span>
            <span className="stat-change up">↑ +1.4% than yesterday</span>
          </div>
          <div className="stat-icon-box" style={{ '--icon-color': 'var(--zoho-green)' }}>
            <CheckCircle size={20} />
          </div>
        </div>

        {/* Active Lines */}
        <div className="glass-card stat-card" style={{ '--accent-gradient': 'var(--zoho-orange)' }}>
          <div className="stat-info">
            <span className="stat-label">Live Channels Active</span>
            <span className="stat-value">{metrics.activeCalls}</span>
            <span className="stat-change up" style={{ color: 'var(--zoho-orange)' }}>Running Telephony Pool</span>
          </div>
          <div className="stat-icon-box" style={{ '--icon-color': 'var(--zoho-orange)' }}>
            <Activity size={20} />
          </div>
        </div>
      </div>

      {/* Main Grid: Telemetry Trends & Call Initiator */}
      <div className="dashboard-grid">
        {/* Latency Pipeline Visualizer */}
        <div className="glass-card">
          <div className="card-header">
            <div className="card-title">
              <Activity size={18} style={{ color: 'var(--zoho-blue)' }} />
              <span>Voice Pipeline Latency Breakdown (Live)</span>
            </div>
            <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Target threshold: &lt; 1.5s response loop</span>
          </div>
          
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '1rem', marginBottom: '2rem' }}>
            <div style={{ background: '#f8fafc', border: '1px solid var(--border-color)', borderRadius: '8px', padding: '1rem' }}>
              <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>STT Service (Sarvam)</div>
              <div style={{ fontSize: '1.5rem', fontWeight: 'bold', color: 'var(--text-primary)', margin: '0.25rem 0' }}>{metrics.sttLatency}</div>
              <div className="mini-chart">
                <div className="mini-chart-bar" style={{ height: '35%' }}></div>
                <div className="mini-chart-bar" style={{ height: '50%' }}></div>
                <div className="mini-chart-bar" style={{ height: '40%' }}></div>
                <div className="mini-chart-bar" style={{ height: '65%' }}></div>
                <div className="mini-chart-bar" style={{ height: '50%' }}></div>
                <div className="mini-chart-bar" style={{ height: '45%' }}></div>
              </div>
            </div>

            <div style={{ background: '#f8fafc', border: '1px solid var(--border-color)', borderRadius: '8px', padding: '1rem' }}>
              <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>LLM AI Agent (DeepSeek/Gemini)</div>
              <div style={{ fontSize: '1.5rem', fontWeight: 'bold', color: 'var(--zoho-blue)', margin: '0.25rem 0' }}>{metrics.llmLatency}</div>
              <div className="mini-chart">
                <div className="mini-chart-bar" style={{ height: '70%', background: 'var(--zoho-blue)' }}></div>
                <div className="mini-chart-bar" style={{ height: '60%', background: 'var(--zoho-blue)' }}></div>
                <div className="mini-chart-bar" style={{ height: '80%', background: 'var(--zoho-blue)' }}></div>
                <div className="mini-chart-bar" style={{ height: '55%', background: 'var(--zoho-blue)' }}></div>
                <div className="mini-chart-bar" style={{ height: '65%', background: 'var(--zoho-blue)' }}></div>
                <div className="mini-chart-bar" style={{ height: '60%', background: 'var(--zoho-blue)' }}></div>
              </div>
            </div>

            <div style={{ background: '#f8fafc', border: '1px solid var(--border-color)', borderRadius: '8px', padding: '1rem' }}>
              <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>TTS Service (Edge/Vits)</div>
              <div style={{ fontSize: '1.5rem', fontWeight: 'bold', color: 'var(--zoho-teal)', margin: '0.25rem 0' }}>{metrics.ttsLatency}</div>
              <div className="mini-chart">
                <div className="mini-chart-bar" style={{ height: '40%', background: 'var(--zoho-teal)' }}></div>
                <div className="mini-chart-bar" style={{ height: '45%', background: 'var(--zoho-teal)' }}></div>
                <div className="mini-chart-bar" style={{ height: '30%', background: 'var(--zoho-teal)' }}></div>
                <div className="mini-chart-bar" style={{ height: '50%', background: 'var(--zoho-teal)' }}></div>
                <div className="mini-chart-bar" style={{ height: '35%', background: 'var(--zoho-teal)' }}></div>
                <div className="mini-chart-bar" style={{ height: '40%', background: 'var(--zoho-teal)' }}></div>
              </div>
            </div>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.8rem', color: 'var(--text-secondary)', padding: '0.75rem', background: 'var(--zoho-blue-light)', borderRadius: '8px', border: '1px solid rgba(27, 115, 232, 0.15)' }}>
            <Activity size={14} style={{ color: 'var(--zoho-blue)' }} />
            <span>AI pipelines are optimizing chunk sizes automatically to minimize TTFB (Time To First Byte).</span>
          </div>
        </div>

      </div>

      {/* Recent Activity Table and Auditor Panel */}
      <div className="glass-card" style={{ padding: '1.5rem' }}>
        <div className="card-header">
          <div className="card-title">
            <History size={18} style={{ color: 'var(--zoho-blue)' }} />
            <span>Recent Telephony Call Sessions</span>
          </div>
          <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>Click on a session to inspect telemetry details</span>
        </div>

        <div className="table-wrapper">
          <table className="custom-table">
            <thead>
              <tr>
                <th>Caller / Lead</th>
                <th>Phone Number</th>
                <th>Duration</th>
                <th>Time (UTC)</th>
                <th>Status</th>
                <th>Telemetry Latency</th>
                <th>Inspection</th>
              </tr>
            </thead>
            <tbody>
              {calls.map((call) => (
                <tr 
                  key={call.id} 
                  onClick={() => setSelectedCall(selectedCall?.id === call.id ? null : call)}
                  style={{ cursor: 'pointer', background: selectedCall?.id === call.id ? 'var(--zoho-blue-light)' : '' }}
                >
                  <td style={{ fontWeight: 600 }}>{call.caller_name}</td>
                  <td>{call.phone_number}</td>
                  <td>
                    {call.status === 'In Progress' ? (
                      <div className="waveform">
                        <div className="wave-bar"></div>
                        <div className="wave-bar"></div>
                        <div className="wave-bar"></div>
                        <div className="wave-bar"></div>
                        <span style={{ fontSize: '0.8rem', color: 'var(--zoho-orange)', marginLeft: '0.25rem' }}>Live</span>
                      </div>
                    ) : (
                      `${call.call_duration}s`
                    )}
                  </td>
                  <td>{new Date(call.created_at).toLocaleTimeString()}</td>
                  <td>
                    <span className={`badge ${getStatusBadgeClass(call.status)}`}>
                      {call.status}
                    </span>
                  </td>
                  <td>
                    {call.status === 'In Progress' ? (
                      <span style={{ color: 'var(--text-muted)', fontSize: '0.8rem' }}>Evaluating...</span>
                    ) : (
                      <span style={{ color: 'var(--zoho-teal)', fontWeight: 500 }}>{call.latency.total}</span>
                    )}
                  </td>
                  <td>
                    <button className="icon-btn" onClick={(e) => {
                      e.stopPropagation();
                      setSelectedCall(selectedCall?.id === call.id ? null : call);
                    }}>
                      <Eye size={14} />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Selected Call Detail Viewer */}
        {selectedCall && (
          <div className="call-log-inspect" style={{ animation: 'fadeIn 0.25s ease' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.75rem', borderBottom: '1px solid var(--border-color)', paddingBottom: '0.5rem' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <CornerDownRight size={16} style={{ color: 'var(--zoho-blue)' }} />
                <h4 style={{ fontSize: '0.95rem', fontWeight: 600 }}>Debugging Session ID: {selectedCall.id} ({selectedCall.caller_name})</h4>
              </div>
              <button 
                style={{ background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', fontSize: '0.8rem' }}
                onClick={() => setSelectedCall(null)}
              >
                Close Panel [x]
              </button>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1.2fr 1fr', gap: '1rem' }}>
              <div>
                <span style={{ display: 'block', fontSize: '0.8rem', color: 'var(--text-secondary)', marginBottom: '0.25rem' }}>Dialogue Pipeline Log:</span>
                <div className="transcript-bubble">
                  {selectedCall.transcript}
                </div>
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                <span style={{ display: 'block', fontSize: '0.8rem', color: 'var(--text-secondary)' }}>System Pipeline Analysis:</span>
                <div style={{ background: '#f8fafc', padding: '0.75rem', borderRadius: '8px', border: '1px solid var(--border-color)' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.8rem', paddingBottom: '0.25rem', borderBottom: '1px solid var(--border-color)' }}>
                    <span>STT Time to Transcription:</span>
                    <strong style={{ color: 'var(--zoho-teal)' }}>{selectedCall.latency.stt}</strong>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.8rem', padding: '0.25rem 0', borderBottom: '1px solid var(--border-color)' }}>
                    <span>LLM Agent Choice:</span>
                    <strong style={{ color: 'var(--zoho-blue)' }}>{selectedCall.latency.llm}</strong>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.8rem', padding: '0.25rem 0', borderBottom: '1px solid var(--border-color)' }}>
                    <span>TTS Streaming Output:</span>
                    <strong style={{ color: 'var(--zoho-teal)' }}>{selectedCall.latency.tts}</strong>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.8rem', paddingTop: '0.25rem', fontWeight: 600 }}>
                    <span>Total Audio Round-trip:</span>
                    <span style={{ color: 'var(--text-primary)' }}>{selectedCall.latency.total}</span>
                  </div>
                </div>

                <div style={{ background: 'var(--zoho-purple-light)', padding: '0.75rem', borderRadius: '8px', border: '1px solid rgba(124, 77, 255, 0.15)' }}>
                  <div style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--zoho-purple)', marginBottom: '0.25rem' }}>AI Action Outcome:</div>
                  <p style={{ fontSize: '0.8rem', color: 'var(--text-primary)', fontStyle: 'italic' }}>
                    "{selectedCall.ai_response}"
                  </p>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default Dashboard;
