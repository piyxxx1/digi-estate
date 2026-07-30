import { useState, useRef, useEffect } from 'react';
import { PhoneCall, Square, Mic, X, Volume2, Play, History } from 'lucide-react';
import type { Lead, Message } from '../types';

interface DialerModalProps {
  activeCallLead: Lead;
  onClose: (didUpdate?: boolean) => void;
}

export function DialerModal({ activeCallLead, onClose }: DialerModalProps) {
  const [callState, setCallState] = useState<'idle' | 'calling' | 'connected' | 'ended'>('idle');
  const [messages, setMessages] = useState<Message[]>([]);
  const [historyMessages, setHistoryMessages] = useState<Message[]>([]);
  const [showHistory, setShowHistory] = useState(false);
  const [recordingTime, setRecordingTime] = useState(0);
  const realtimeTranscript = '';
  const [hasUpdated, setHasUpdated] = useState(false);
  const [activeCallSid, setActiveCallSid] = useState<string | null>(null);

  const socketRef = useRef<WebSocket | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const processorRef = useRef<ScriptProcessorNode | null>(null);
  const timerRef = useRef<number | null>(null);
  const pollTimerRef = useRef<number | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, realtimeTranscript]);

  // Clean up on unmount (prevent memory/audio leaks if user force closes the modal)
  useEffect(() => {
    return () => {
      cleanupAudioSession();
    };
  }, []);

  // Fetch past conversation history from PostgreSQL when popup opens
  useEffect(() => {
    const fetchHistory = async () => {
      try {
        const API_BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";
        const response = await fetch(`${API_BASE_URL}/api/calls/history/${encodeURIComponent(activeCallLead.phone)}`);
        if (response.ok) {
          const data = await response.json();
          if (data.messages && data.messages.length > 0) {
            const historyMsgs = data.messages.map((m: any, idx: number) => ({
              id: idx,
              text: m.text,
              sender: m.role === 'assistant' ? 'bot' : 'user',
              time: m.time || ''
            }));
            
            setHistoryMessages(historyMsgs);
          }
        }
      } catch (error) {
        console.error("Failed to fetch history:", error);
      }
    };
    fetchHistory();
  }, [activeCallLead.phone]);

  const cleanupAudioSession = () => {
    if (processorRef.current) {
      processorRef.current.disconnect();
      processorRef.current = null;
    }
    if (audioContextRef.current) {
      if (audioContextRef.current.state !== 'closed') {
        audioContextRef.current.close();
      }
      audioContextRef.current = null;
    }
    if (socketRef.current) {
      if (socketRef.current.readyState === WebSocket.OPEN) {
        socketRef.current.close();
      }
      socketRef.current = null;
    }
    if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
    if (pollTimerRef.current) {
      clearInterval(pollTimerRef.current);
      pollTimerRef.current = null;
    }
  };

  const startVoiceCall = async () => {
    setCallState('calling');
    setMessages([
      {
        id: Date.now(),
        text: `Initiating API request to Exotel... Dialing ${activeCallLead.name} (${activeCallLead.phone}).`,
        sender: 'bot',
        time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
      }
    ]);

    try {
      const userObj = JSON.parse(localStorage.getItem('user') || '{}');
      if (!userObj.user_id) {
        throw new Error("No user session found. Please re-login.");
      }

      const API_BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";
      const response = await fetch(`${API_BASE_URL}/api/calls/outbound-ai`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_id: userObj.user_id,
          lead_phone: activeCallLead.phone
        })
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || "API request failed.");
      }

      const result = await response.json();
      const callSid = result.details?.Call?.Sid || result.details?.sid || result.details?.Call?.sid;
      
      if (callSid) {
        setActiveCallSid(callSid);
      }

      setCallState('connected');
      setMessages(prev => [
        ...prev,
        {
          id: Date.now() + 1,
          text: `Exotel API initiated successfully (Call SID: ${callSid || 'Unknown'})! The lead's phone is now ringing. Once they answer, you will see the live transcript from Sarvam below.`,
          sender: 'bot',
          time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
        }
      ]);

      setRecordingTime(0);
      timerRef.current = window.setInterval(() => {
        setRecordingTime(prev => prev + 1);
      }, 1000);

      if (callSid) {
        pollTimerRef.current = window.setInterval(async () => {
          try {
            const transcriptRes = await fetch(`${API_BASE_URL}/api/calls/live-transcript/${callSid}`);
            if (transcriptRes.ok) {
              const data = await transcriptRes.json();
              if (data.messages && data.messages.length > 0) {
                // Map the memory history to our message UI state
                const mappedMessages = data.messages.map((m: any, idx: number) => ({
                  id: 10000 + idx, // offset so it doesn't collide with initial messages
                  text: m.text,
                  sender: m.role === 'assistant' ? 'bot' : 'user',
                  time: ''
                }));
                
                // Preserve the initial 2 informative messages
                setMessages(prev => {
                  const initialMsgs = prev.filter(p => p.id < 10000);
                  return [...initialMsgs, ...mappedMessages];
                });
              }
              
              // Check if call has ended based on status from the backend
              if (data.status && !['in-progress', 'queued', 'ringing'].includes(data.status.toLowerCase())) {
                setCallState('ended');
                setMessages(prev => [
                  ...prev,
                  {
                    id: Date.now() + 2,
                    text: `[Call Ended] Status: ${data.status}`,
                    sender: 'bot',
                    time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
                  }
                ]);
                
                if (timerRef.current) {
                  clearInterval(timerRef.current);
                  timerRef.current = null;
                }
                if (pollTimerRef.current) {
                  clearInterval(pollTimerRef.current);
                  pollTimerRef.current = null;
                }
                setHasUpdated(true);
              }
            }
          } catch (err) {
            console.error("Live transcript fetch failed:", err);
          }
        }, 1500); // Poll every 1.5s
      }

    } catch (err: any) {
      console.error("Outbound Call Initialization Failed:", err);
      alert("Failed to initiate outbound call: " + err.message);
      setCallState('idle');
    }
  };

  const endVoiceCall = async () => {
    setCallState('ended');
    
    if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
    if (pollTimerRef.current) {
      clearInterval(pollTimerRef.current);
      pollTimerRef.current = null;
    }

    const API_BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

    try {
      // Force terminate the ongoing Exotel websocket stream
      if (activeCallSid) {
        await fetch(`${API_BASE_URL}/calls/${activeCallSid}/terminate`, {
          method: "POST"
        });
      }

      // Update Lead Status to 'Connected' in DB
      const leadStatusResponse = await fetch(`${API_BASE_URL}/api/leads/${activeCallLead.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status: "Connected" })
      });

      if (leadStatusResponse.ok) {
        setHasUpdated(true);
      }
    } catch (e) {
      console.error("Failed to update database after call end:", e);
    }
  };

  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  const playAudio = (base64Audio: string) => {
    const audio = new Audio(`data:audio/mpeg;base64,${base64Audio}`);
    audio.play().catch(e => console.error("Audio playback error:", e));
  };

  return (
    <div className="dialer-overlay">
      <div className="dialer-modal">
        {/* Left dialer status panel */}
        <div className="dialer-left">
          <div className="dialer-lead-info">
            <div className={`dialer-avatar ${callState}`}>
              <PhoneCall size={32} color="white" />
            </div>
            <h3 className="dialer-lead-name">{activeCallLead.name}</h3>
            <span className="dialer-lead-phone">{activeCallLead.phone}</span>
          </div>

          <div className="dialer-status">
            <span className="dialer-status-label">Agent connection</span>
            <span className={`dialer-status-val ${callState}`}>
              {callState === 'idle' && 'Ready to dial'}
              {callState === 'calling' && 'Calling...'}
              {callState === 'connected' && 'Connected (Voice Stream Active)'}
              {callState === 'ended' && 'Call Hang Up'}
            </span>

            {/* Animated waves if connected */}
            {callState === 'connected' && (
              <div style={{ display: 'flex', justifyContent: 'center' }}>
                <div className="dialer-audio-wave">
                  <span></span><span></span><span></span><span></span><span></span>
                </div>
              </div>
            )}
          </div>

          <div className="dialer-controls">
            {callState === 'idle' || callState === 'ended' ? (
              <button
                className="btn-dialer-action start-call"
                onClick={startVoiceCall}
              >
                <Mic size={18} />
                <span>Dial Client</span>
              </button>
            ) : (
              <button
                className="btn-dialer-action hangup"
                onClick={endVoiceCall}
              >
                <Square size={16} fill="currentColor" />
                <span>Hang Up</span>
              </button>
            )}

            {callState === 'connected' && (
              <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', textAlign: 'center', marginTop: '6px' }}>
                Speaking time: {formatTime(recordingTime)}
              </div>
            )}
          </div>
        </div>

        {/* Right live transcript panel */}
        <div className="dialer-right">
          <div className="dialer-transcript-header">
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <h4>Priya Call Assistant Transcript</h4>
              {historyMessages.length > 0 && (
                <button 
                  className="dialer-history-btn" 
                  onClick={() => setShowHistory(!showHistory)}
                  title="Toggle Past Conversations"
                  style={{ background: 'none', border: 'none', cursor: 'pointer', color: showHistory ? 'var(--primary-color, #4361ee)' : 'var(--text-secondary, #64748b)', display: 'flex', alignItems: 'center' }}
                >
                  <History size={16} />
                </button>
              )}
            </div>
            <button className="dialer-close-btn" onClick={() => onClose(hasUpdated)}>
              <X size={18} />
            </button>
          </div>

          <div className="dialer-transcript-body">
            {showHistory && historyMessages.length > 0 && (
              <div className="history-section" style={{ opacity: 0.85, marginBottom: '16px', borderBottom: '1px dashed var(--border-color, #e2e8f0)', paddingBottom: '16px' }}>
                <div style={{ textAlign: 'center', fontSize: '0.75rem', color: 'var(--text-secondary, #64748b)', marginBottom: '12px' }}>
                  --- Previous Conversation History ---
                </div>
                {historyMessages.map((msg) => (
                  <div
                    key={`hist-${msg.id}`}
                    className={`dialer-msg ${msg.sender === 'user' ? 'lead' : 'priya'}`}
                  >
                    <span className="dialer-msg-speaker">
                      {msg.sender === 'user' ? 'Client (Lead)' : 'Priya (AI)'}
                      {msg.time && <span style={{ marginLeft: '6px', fontSize: '0.65rem', fontWeight: 'normal' }}>{msg.time}</span>}
                    </span>
                    <div className="dialer-msg-bubble">
                      {msg.text}
                    </div>
                  </div>
                ))}
              </div>
            )}

            {messages.length > 0 ? (
              messages.map((msg) => (
                <div
                  key={msg.id}
                  className={`dialer-msg ${msg.sender === 'user' ? 'lead' : 'priya'}`}
                >
                  <span className="dialer-msg-speaker">
                    {msg.sender === 'user' ? 'Client (Lead)' : 'Priya (AI)'}
                  </span>
                  <div className="dialer-msg-bubble">
                    {msg.text}
                    {msg.sender === 'bot' && msg.audio && (
                      <button
                        className="play-message-btn"
                        onClick={() => playAudio(msg.audio!)}
                        title="Replay speech chunk"
                        style={{ display: 'inline-flex', verticalAlign: 'middle', marginLeft: '8px' }}
                      >
                        <Play size={10} fill="currentColor" />
                      </button>
                    )}
                  </div>
                </div>
              ))
            ) : (
              <div className="dialer-transcript-empty">
                <Volume2 size={36} className={callState === 'connected' ? 'realtime-pulse-mic' : ''} />
                {callState === 'idle' ? (
                  <p>Click "Dial Client" to start communicating via voice websocket.</p>
                ) : callState === 'calling' ? (
                  <p>Connecting voice pipelines... please wait.</p>
                ) : (
                  <p>Active audio conversation transcript will appear here in real-time.</p>
                )}
              </div>
            )}

            {/* Real-time transcript preview */}
            {realtimeTranscript && (
              <div className="dialer-msg lead" style={{ opacity: 0.7 }}>
                <span className="dialer-msg-speaker">Client (Speaking...)</span>
                <div className="dialer-msg-bubble" style={{ fontStyle: 'italic' }}>
                  {realtimeTranscript}
                </div>
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>
        </div>

      </div>
    </div>
  );
}
