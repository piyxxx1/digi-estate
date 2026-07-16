import { useState, useEffect, useCallback } from 'react';
import { 
  PhoneIncoming, 
  PhoneOutgoing, 
  ChevronDown, 
  ChevronUp, 
  MessageSquare, 
  Clock
} from 'lucide-react';
import type { CallLog } from '../types';

interface CallsTabProps {
  currentUser: { user_id: string; business_name: string };
  searchQuery: string;
  refreshTrigger: number;
}

export function CallsTab({ currentUser, searchQuery, refreshTrigger }: CallsTabProps) {
  const [callLogs, setCallLogs] = useState<CallLog[]>([]);
  const [assignedNumber, setAssignedNumber] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState('');

  const API_BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

  const loadCallLogs = useCallback(async () => {
    if (!currentUser) return;
    setIsLoading(true);
    setError('');

    try {
      // Step 1: Look up the user's assigned ExoPhone from the users list
      const usersRes = await fetch(`${API_BASE_URL}/api/users`);
      let exophone: string | null = null;
      if (usersRes.ok) {
        const users = await usersRes.json();
        const me = users.find((u: any) => u.user_id === currentUser.user_id);
        exophone = me?.exotel_virtual_number || null;
        setAssignedNumber(exophone);
      }

      if (!exophone) {
        setCallLogs([]);
        setError('No ExoPhone number is assigned to your account. Contact your administrator.');
        return;
      }

      // Step 2: Fetch Exotel calls filtered by the assigned ExoPhone
      const callsRes = await fetch(
        `${API_BASE_URL}/api/exotel/calls-by-number?virtual_number=${encodeURIComponent(exophone)}`
      );

      if (!callsRes.ok) {
        setError('Failed to fetch call history from Exotel.');
        return;
      }

      const data = await callsRes.json();
      const calls = data.calls || [];

      const mapped = calls.map((item: any, idx: number) => ({
        id: idx,
        leadName: item.From || item.To || 'Unknown',
        fromPhone: item.From || 'Unknown',
        toPhone: item.To || 'Unknown',
        date: item.StartTime
          ? new Date(item.StartTime).toLocaleString('en-IN', {
              year: 'numeric', month: '2-digit', day: '2-digit',
              hour: '2-digit', minute: '2-digit', hour12: false
            })
          : 'N/A',
        duration: item.Duration ? `${Math.floor(Number(item.Duration) / 60)}m ${Number(item.Duration) % 60}s` : '0s',
        status: item.Status || 'completed',
        summary: item.RecordingUrl ? `Recording: ${item.RecordingUrl}` : 'No recording.',
        direction: item.Direction || (item.From === exophone ? 'Outgoing' : 'Incoming'),
        flowName: item.PhoneNumberSid || item.CallType || 'AI_FLOW',
        outcome: item.Status || 'completed',
        callSid: item.Sid || '',
        transcript: ''
      }));

      setCallLogs(mapped);
    } catch (err) {
      console.error("Failed to load call logs:", err);
      setError('Network error while fetching call history.');
    } finally {
      setIsLoading(false);
    }
  }, [currentUser, API_BASE_URL]);

  useEffect(() => {
    loadCallLogs();
  }, [loadCallLogs, refreshTrigger]);

  const filteredLogs = callLogs.filter(log =>
    log.leadName.toLowerCase().includes(searchQuery.toLowerCase()) ||
    log.phone.includes(searchQuery) ||
    log.summary.toLowerCase().includes(searchQuery.toLowerCase()) ||
    (log.outcome && log.outcome.toLowerCase().includes(searchQuery.toLowerCase()))
  );

  // Helper to format duration to hh:mm:ss format
  const formatDuration = (durationStr: string) => {
    if (!durationStr) return "00:00:00";
    
    // Parse duration string: e.g. "1m 35s" or "35s" or "1:35" or integer seconds
    let totalSecs = 0;
    const minMatch = durationStr.match(/(\d+)m/);
    const secMatch = durationStr.match(/(\d+)s/);
    const colonMatch = durationStr.match(/(\d+):(\d+)/);
    
    if (minMatch) totalSecs += parseInt(minMatch[1]) * 60;
    if (secMatch) totalSecs += parseInt(secMatch[1]);
    if (colonMatch && !minMatch && !secMatch) {
      totalSecs += parseInt(colonMatch[1]) * 60 + parseInt(colonMatch[2]);
    }
    
    if (totalSecs === 0) {
      const rawVal = parseInt(durationStr);
      if (!isNaN(rawVal)) totalSecs = rawVal;
    }

    const h = Math.floor(totalSecs / 3600);
    const m = Math.floor((totalSecs % 3600) / 60);
    const s = totalSecs % 60;
    return `${h.toString().padStart(2, '0')}:${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
  };

  return (
    <div className="section-panel" style={{ background: 'var(--panel-bg)', borderRadius: '16px', border: '1px solid var(--border-color)', overflow: 'hidden' }}>
      <div className="panel-header" style={{ borderBottom: '1px solid var(--border-color)', padding: '20px 24px', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div>
          <h3 style={{ margin: 0, fontSize: '1.25rem', fontWeight: 700, color: 'black' }}>
            Telephony Call Log History
          </h3>
          {assignedNumber && (
            <p style={{ margin: '4px 0 0', fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
              Showing calls for ExoPhone: <code style={{ background: 'rgba(255,255,255,0.06)', padding: '2px 6px', borderRadius: 4, color: '#a78bfa' }}>{assignedNumber}</code>
            </p>
          )}
        </div>
      </div>

      {isLoading ? (
        <div style={{ textAlign: 'center', padding: '4rem', color: 'var(--text-secondary)' }}>
          <div style={{ width: 36, height: 36, border: '3px solid #a78bfa', borderTopColor: 'transparent', borderRadius: '50%', animation: 'spin 0.8s linear infinite', margin: '0 auto 1rem' }} />
          <p>Fetching call history from Exotel...</p>
        </div>
      ) : error ? (
        <div style={{ textAlign: 'center', padding: '4rem', color: '#f59e0b' }}>
          <p style={{ fontSize: '1rem' }}>⚠️ {error}</p>
        </div>
      ) : (
        <table className="crm-table" style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left' }}>
          <thead>
            <tr style={{ borderBottom: '2px solid var(--border-color)', background: 'rgba(255,255,255,0.01)' }}>
              <th style={{ padding: '14px 20px', color: 'var(--text-secondary)', fontWeight: 600, fontSize: '0.85rem' }}>FROM</th>
              <th style={{ padding: '14px 20px', color: 'var(--text-secondary)', fontWeight: 600, fontSize: '0.85rem' }}>TO</th>
              <th style={{ padding: '14px 20px', color: 'var(--text-secondary)', fontWeight: 600, fontSize: '0.85rem' }}>DIRECTION</th>
              <th style={{ padding: '14px 20px', color: 'var(--text-secondary)', fontWeight: 600, fontSize: '0.85rem' }}>TIME</th>
              <th style={{ padding: '14px 20px', color: 'var(--text-secondary)', fontWeight: 600, fontSize: '0.85rem' }}>OUTCOME</th>
              <th style={{ padding: '14px 20px', color: 'var(--text-secondary)', fontWeight: 600, fontSize: '0.85rem' }}>CALL DURATION</th>
            </tr>
          </thead>
          <tbody>
            {filteredLogs.length > 0 ? (
              filteredLogs.map((log) => {
                const dirLower = (log.direction || "").toLowerCase();
                const isIncoming = dirLower === 'incoming' || dirLower === 'inbound';
                const displayDirection = dirLower === 'inbound' ? 'Inbound' : dirLower === 'outbound' ? 'Outbound' : (log.direction || "Incoming");

                return (
                  <tr 
                    key={log.id} 
                    style={{ 
                      borderBottom: '1px solid var(--border-color)', 
                      transition: 'background-color 0.2s',
                    }}
                    className="call-log-row"
                  >
                      {/* FROM */}
                      <td style={{ padding: '16px 20px' }}>
                        <code style={{ 
                          background: 'rgba(167, 139, 250, 0.1)', 
                          padding: '6px 10px', 
                          borderRadius: '6px', 
                          fontSize: '0.85rem',
                          fontWeight: 600,
                          color: 'var(--text-primary)',
                          border: '1px solid rgba(167, 139, 250, 0.2)'
                        }}>
                          {log.fromPhone}
                        </code>
                      </td>

                      {/* TO */}
                      <td style={{ padding: '16px 20px' }}>
                        <code style={{ 
                          background: 'rgba(167, 139, 250, 0.1)', 
                          padding: '6px 10px', 
                          borderRadius: '6px', 
                          fontSize: '0.85rem',
                          fontWeight: 600,
                          color: 'var(--text-primary)',
                          border: '1px solid rgba(167, 139, 250, 0.2)'
                        }}>
                          {log.toPhone}
                        </code>
                      </td>

                      {/* DIRECTION */}
                      <td style={{ padding: '16px 20px' }}>
                        <span style={{ 
                          display: 'inline-flex',
                          alignItems: 'center',
                          gap: '6px',
                          padding: '4px 10px',
                          borderRadius: '20px',
                          fontSize: '0.75rem',
                          fontWeight: 600,
                          backgroundColor: isIncoming ? 'rgba(239, 68, 68, 0.1)' : 'rgba(16, 185, 129, 0.1)',
                          color: isIncoming ? '#ef4444' : '#10b981',
                          border: `1px solid ${isIncoming ? 'rgba(239, 68, 68, 0.2)' : 'rgba(16, 185, 129, 0.2)'}`
                        }}>
                          {isIncoming ? <PhoneIncoming size={12} /> : <PhoneOutgoing size={12} />}
                          {displayDirection}
                        </span>
                      </td>

                      {/* TIME */}
                      <td style={{ padding: '16px 20px', color: 'var(--text-secondary)', fontSize: '0.85rem' }}>
                        {log.date}
                      </td>

                      {/* OUTCOME */}
                      <td style={{ padding: '16px 20px' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                          <span style={{
                            width: '8px',
                            height: '8px',
                            borderRadius: '50%',
                            backgroundColor: (log.outcome || "").toLowerCase() === 'completed' ? '#10b981' : '#f59e0b'
                          }} />
                          <span style={{ 
                            fontSize: '0.85rem', 
                            color: 'var(--text-primary)',
                            maxWidth: '180px',
                            overflow: 'hidden',
                            textOverflow: 'ellipsis',
                            whiteSpace: 'nowrap'
                          }} title={log.outcome}>
                            {log.outcome || "Completed"}
                          </span>
                        </div>
                      </td>

                      <td style={{ padding: '16px 20px' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--text-primary)', fontWeight: 500 }}>
                          <Clock size={14} style={{ color: 'var(--text-secondary)' }} />
                          {formatDuration(log.duration)}
                        </div>
                      </td>
                    </tr>
                );
              })
            ) : (
              <tr>
                <td colSpan={8} style={{ textAlign: 'center', padding: '30px', color: 'var(--text-secondary)' }}>
                  No call logs matched the query.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      )}
    </div>
  );
}
