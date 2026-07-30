import { useState, useEffect } from 'react';
import { X, History, ChevronRight, ArrowLeft, Calendar } from 'lucide-react';
import type { Lead } from '../types';

interface HistoryModalProps {
  lead: Lead;
  onClose: () => void;
}

const formatDuration = (seconds?: number) => {
  if (seconds === undefined || seconds === null) return null;
  if (seconds < 60) return `${seconds}s`;
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${m}m ${s}s`;
};

export function HistoryModal({ lead, onClose }: HistoryModalProps) {
  const [historyCalls, setHistoryCalls] = useState<any[][]>([]);
  const [activeCallIdx, setActiveCallIdx] = useState<number | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const fetchHistory = async () => {
      try {
        const API_BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";
        const response = await fetch(`${API_BASE_URL}/api/calls/history/${encodeURIComponent(lead.phone)}`);
        if (response.ok) {
          const data = await response.json();
          if (data.messages && data.messages.length > 0) {
            const historyMsgs = data.messages.map((m: any, idx: number) => ({
              id: idx,
              text: m.text,
              sender: m.role === 'assistant' ? 'bot' : 'user',
              time: m.time || '',
              date: m.date || '',
              timestamp: m.timestamp || '',
              call_sid: m.call_sid || null,
              call_duration: m.call_duration || null
            }));
            
            const calls: any[][] = [];
            let currentCall: any[] = [];
            let currentCallSid: string | null = null;
            
            for (let i = 0; i < historyMsgs.length; i++) {
               const msg = historyMsgs[i];
               
               let startNewCall = false;
               if (currentCall.length > 0) {
                   if (msg.call_sid && msg.call_sid !== currentCallSid) {
                       startNewCall = true;
                   } else if (!msg.call_sid && currentCallSid) {
                       startNewCall = true;
                   }
               }
               
               if (startNewCall) {
                   calls.push([...currentCall]);
                   currentCall = [];
               }
               
               currentCall.push(msg);
               currentCallSid = msg.call_sid;
               
               if (!msg.call_sid) {
                   if (msg.text.includes('[Call Ended]')) {
                       calls.push([...currentCall]);
                       currentCall = [];
                       currentCallSid = null;
                   } else if (i < historyMsgs.length - 1) {
                       const nextMsg = historyMsgs[i + 1];
                       if (!nextMsg.call_sid) {
                           const t1 = new Date(msg.timestamp).getTime();
                           const t2 = new Date(nextMsg.timestamp).getTime();
                           if (t2 - t1 > 5 * 60 * 1000) {
                               calls.push([...currentCall]);
                               currentCall = [];
                               currentCallSid = null;
                           }
                       }
                   }
               }
            }
            if (currentCall.length > 0) {
               calls.push(currentCall);
            }
            setHistoryCalls(calls);
          }
        }
      } catch (error) {
        console.error("Failed to fetch history:", error);
      } finally {
        setIsLoading(false);
      }
    };
    fetchHistory();
  }, [lead.phone]);

  return (
    <div className="dialer-overlay" onClick={onClose} style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', backgroundColor: 'rgba(0, 0, 0, 0.5)', backdropFilter: 'blur(5px)', position: 'fixed', inset: 0, zIndex: 999 }}>
      <div className="dialer-modal" onClick={e => e.stopPropagation()} style={{ width: '650px', maxWidth: '95%', height: '85vh', display: 'flex', flexDirection: 'column', background: 'var(--bg-surface, #ffffff)', borderRadius: '20px', boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.5), 0 0 0 1px rgba(255,255,255,0.1)', overflow: 'hidden' }}>
        <div className="dialer-transcript-header" style={{ padding: '24px 30px', borderBottom: '1px solid var(--border-color)', display: 'flex', justifyContent: 'space-between', alignItems: 'center', background: 'var(--bg-surface, #ffffff)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
            {activeCallIdx !== null ? (
              <button 
                onClick={() => setActiveCallIdx(null)}
                style={{ 
                  background: 'var(--bg-app, #f4f5f7)', border: 'none', cursor: 'pointer', color: 'var(--text-secondary)', width: '40px', height: '40px', borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center', transition: 'background 0.2s', marginRight: '4px'
                }}>
                <ArrowLeft size={20} />
              </button>
            ) : (
              <div style={{ width: '48px', height: '48px', borderRadius: '12px', background: 'linear-gradient(135deg, var(--primary, #0052cc) 0%, #337ab7 100%)', color: '#fff', display: 'flex', alignItems: 'center', justifyContent: 'center', boxShadow: '0 8px 16px rgba(0, 82, 204, 0.25)' }}>
                <History size={24} />
              </div>
            )}
            <div>
              <h4 style={{ margin: 0, fontSize: '1.25rem', fontWeight: 600, color: 'var(--text-primary)', letterSpacing: '-0.01em' }}>
                {activeCallIdx !== null ? `Conversation ${activeCallIdx + 1}` : 'Conversation History'}
              </h4>
              <div style={{ fontSize: '0.9rem', color: 'var(--text-secondary)', marginTop: '4px' }}>
                {activeCallIdx !== null 
                  ? historyCalls[activeCallIdx]?.[0]?.date 
                  : <>{lead.name} &bull; <span style={{ opacity: 0.8 }}>{lead.phone}</span></>}
              </div>
            </div>
          </div>
          <button className="dialer-close-btn" onClick={onClose} style={{ background: 'var(--bg-app, #f4f5f7)', border: 'none', cursor: 'pointer', color: 'var(--text-secondary)', width: '36px', height: '36px', borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center', transition: 'background 0.2s' }}>
            <X size={18} />
          </button>
        </div>
        
        <div className="dialer-transcript-body" style={{ flex: 1, overflowY: 'auto', padding: '30px', background: 'var(--bg-app, #f4f6f8)' }}>
          {isLoading ? (
            <div style={{ textAlign: 'center', color: 'var(--text-secondary)', padding: '60px', display: 'flex', flexDirection: 'column', gap: '16px', alignItems: 'center' }}>
              <div className="spinner" style={{ width: '30px', height: '30px', border: '3px solid var(--border-color)', borderTopColor: 'var(--primary)', borderRadius: '50%', animation: 'spin 1s linear infinite' }}></div>
              Loading history...
            </div>
          ) : historyCalls.length > 0 ? (
            activeCallIdx === null ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                {historyCalls.map((callMsgs, callIdx) => (
                  <div 
                    key={`call-list-${callIdx}`}
                    onClick={() => setActiveCallIdx(callIdx)}
                    style={{
                      background: 'var(--bg-surface, #ffffff)',
                      borderRadius: '16px',
                      border: '1px solid var(--border-color, #eaeaea)',
                      padding: '20px',
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                      cursor: 'pointer',
                      boxShadow: '0 4px 12px rgba(0,0,0,0.03)',
                      transition: 'all 0.2s ease',
                      userSelect: 'none'
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
                      <div style={{ width: '44px', height: '44px', borderRadius: '50%', background: 'rgba(0,82,204,0.1)', color: 'var(--primary)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                        <Calendar size={20} />
                      </div>
                      <div>
                        <div style={{ fontSize: '1.05rem', fontWeight: 600, color: 'var(--text-primary)' }}>Conversation {callIdx + 1}</div>
                        <div style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginTop: '4px' }}>
                          {callMsgs[0]?.date || ''} &bull; {callMsgs.length} messages
                          {callMsgs[0]?.call_duration && ` • ${formatDuration(callMsgs[0].call_duration)}`}
                        </div>
                      </div>
                    </div>
                    <div style={{ color: 'var(--text-secondary)' }}>
                      <ChevronRight size={20} />
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column' }}>
                {historyCalls[activeCallIdx].map((msg) => (
                  <div
                    key={`hist-${msg.id}`}
                    className={`dialer-msg ${msg.sender === 'user' ? 'lead' : 'priya'}`}
                    style={{
                      display: 'flex',
                      flexDirection: 'column',
                      alignItems: msg.sender === 'user' ? 'flex-end' : 'flex-start',
                      marginBottom: '20px'
                    }}
                  >
                    <span className="dialer-msg-speaker" style={{ fontSize: '0.8rem', fontWeight: 500, color: 'var(--text-secondary)', marginBottom: '6px', padding: '0 4px' }}>
                      {msg.sender === 'user' ? 'Client (Lead)' : 'Priya (AI)'}
                      {msg.time && <span style={{ marginLeft: '8px', fontSize: '0.7rem', opacity: 0.7, fontWeight: 400 }}>{msg.time}</span>}
                    </span>
                    <div className="dialer-msg-bubble" style={{
                      background: msg.sender === 'user' ? 'linear-gradient(135deg, var(--primary, #0052cc) 0%, #337ab7 100%)' : 'var(--bg-surface, #ffffff)',
                      color: msg.sender === 'user' ? '#fff' : 'var(--text-primary)',
                      border: msg.sender === 'user' ? 'none' : '1px solid var(--border-color, #eaeaea)',
                      boxShadow: msg.sender === 'user' ? '0 8px 16px rgba(0, 82, 204, 0.15)' : '0 2px 8px rgba(0,0,0,0.04)',
                      padding: '14px 18px',
                      borderRadius: '16px',
                      borderTopRightRadius: msg.sender === 'user' ? '4px' : '16px',
                      borderTopLeftRadius: msg.sender === 'bot' ? '4px' : '16px',
                      maxWidth: '85%',
                      lineHeight: '1.6',
                      fontSize: '0.95rem'
                    }}>
                      {msg.text}
                    </div>
                  </div>
                ))}
              </div>
            )
          ) : (
            <div style={{ textAlign: 'center', color: 'var(--text-secondary)', padding: '40px', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '16px' }}>
              <History size={48} opacity={0.2} />
              <p>No conversation history found for this lead.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
