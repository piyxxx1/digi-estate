import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Users, Building2, PhoneCall, Sparkles } from 'lucide-react';
import type { Lead, Property, CallLog } from '../types';

interface DashboardTabProps {
  currentUser: { user_id: string; business_name: string };
  refreshTrigger: number;
  onCallLead: (lead: Lead) => void;
}

export function DashboardTab({ currentUser, refreshTrigger, onCallLead }: DashboardTabProps) {
  const navigate = useNavigate();
  const [leads, setLeads] = useState<Lead[]>([]);
  const [properties, setProperties] = useState<Property[]>([]);
  const [callLogs, setCallLogs] = useState<CallLog[]>([]);

  const API_BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

  useEffect(() => {
    const fetchData = async () => {
      try {
        // Fetch properties
        const propRes = await fetch(`${API_BASE_URL}/api/properties?user_id=${currentUser.user_id}`);
        if (propRes.ok) {
          const data = await propRes.json();
          setProperties(data.map((item: any, idx: number) => ({
            id: item.id,
            sequence: idx + 1,
            name: `Property #${idx + 1}`,
            type: "Listing",
            price: "On Request",
            location: "Lansdowne",
            description: item.property_details,
            status: "Available"
          })));
        }

        // Fetch leads
        const leadRes = await fetch(`${API_BASE_URL}/api/leads?user_id=${currentUser.user_id}`);
        if (leadRes.ok) {
          const data = await leadRes.json();
          setLeads(data.map((item: any) => ({
            id: item.lead_id,
            name: item.lead_name,
            phone: item.phone_number,
            status: item.status,
            interest: item.interest,
            date: item.created_at ? item.created_at.substring(0, 10) : "N/A"
          })));
        }

        // Fetch call logs
        const callsRes = await fetch(`${API_BASE_URL}/api/calls?user_id=${currentUser.user_id}`);
        if (callsRes.ok) {
          const data = await callsRes.json();
          setCallLogs(data.map((item: any) => ({
            id: item.id,
            leadName: item.caller_name || "Unknown Lead",
            phone: item.phone_number || "N/A",
            date: item.created_at ? new Date(item.created_at).toLocaleString('en-IN', {
              year: 'numeric',
              month: '2-digit',
              day: '2-digit',
              hour: '2-digit',
              minute: '2-digit',
              hour12: false
            }) : "N/A",
            duration: item.call_duration ? `${Math.floor(item.call_duration / 60)}m ${item.call_duration % 60}s` : "0s",
            status: "Completed",
            summary: item.ai_response || "No summary recorded.",
            toPhone: item.to_phone_number || "N/A",
            direction: item.direction || "Incoming",
            flowName: item.flow_name || "AI_FLOW",
            outcome: item.outcome || "Completed",
            callSid: item.call_sid || "",
            transcript: item.transcript || ""
          })));
        }
      } catch (error) {
        console.error("Failed to load dashboard statistics:", error);
      }
    };

    fetchData();
  }, [currentUser, refreshTrigger]);

  const siteVisitsCount = leads.filter(l => l.status === 'Site Visit Booked').length;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px', padding: '16px 24px', background: 'var(--bg-app)', minHeight: '100%' }}>
      
      {/* HEADER */}
      <div style={{ paddingBottom: '16px', borderBottom: '1px solid var(--border-color)', marginBottom: '8px' }}>
        <h2 style={{ fontSize: '1.4rem', fontWeight: 500, color: 'var(--text-primary)', margin: 0 }}>
          Welcome back, {currentUser.business_name}
        </h2>
        <p style={{ fontSize: '0.9rem', color: 'var(--text-secondary)', margin: '4px 0 0' }}>
          Here's an overview of your real estate AI operations.
        </p>
      </div>

      {/* STAT CARDS */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '16px' }}>
        {[
          { icon: <Users size={20} />, title: 'Total Leads', val: leads.length, sub: '+18% this month', color: 'var(--primary)', onClick: () => navigate('/leads') },
          { icon: <Building2 size={20} />, title: 'Properties', val: properties.length, sub: 'Sequenced portfolio', color: 'var(--accent-green, #36b37e)', onClick: () => navigate('/properties') },
          { icon: <PhoneCall size={20} />, title: 'AI Voice Calls', val: callLogs.length, sub: '98% connection rate', color: '#6554c0', onClick: () => navigate('/calls') },
          { icon: <Sparkles size={20} />, title: 'Site Visits', val: siteVisitsCount, sub: 'High intent rating', color: '#ff991f' },
        ].map((c, i) => (
          <div key={i} onClick={c.onClick} style={{ 
            background: 'var(--bg-surface)', 
            borderRadius: '4px', 
            padding: '20px', 
            border: '1px solid var(--border-color)',
            display: 'flex', flexDirection: 'column', gap: '12px',
            cursor: c.onClick ? 'pointer' : 'default',
            boxShadow: '0 1px 2px rgba(0,0,0,0.05)'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <div style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>{c.title}</div>
              <div style={{ color: c.color }}>{c.icon}</div>
            </div>
            <div>
              <div style={{ fontSize: '2rem', fontWeight: 600, color: 'var(--text-primary)', margin: '0' }}>{c.val}</div>
              <div style={{ fontSize: '0.8rem', color: 'var(--accent-green, #36b37e)', marginTop: '4px' }}>{c.sub}</div>
            </div>
          </div>
        ))}
      </div>

      {/* GRID OF SECTIONS */}
      <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: '20px' }}>
        
        {/* LEADS PANEL */}
        <div style={{ background: 'var(--bg-surface)', borderRadius: '4px', border: '1px solid var(--border-color)', boxShadow: '0 1px 2px rgba(0,0,0,0.05)', display: 'flex', flexDirection: 'column' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '16px 20px', borderBottom: '1px solid var(--border-color)' }}>
            <h3 style={{ margin: 0, fontSize: '1rem', fontWeight: 600, color: 'var(--text-primary)' }}>Recent Lead Profiles</h3>
            <button onClick={() => navigate('/leads')} style={{ background: 'transparent', border: '1px solid var(--border-color)', padding: '4px 12px', borderRadius: '3px', fontSize: '0.8rem', color: 'var(--text-primary)', cursor: 'pointer' }}>View All</button>
          </div>
          
          <div style={{ overflowX: 'auto', padding: '0 20px 20px' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', marginTop: '16px' }}>
              <thead>
                <tr style={{ borderBottom: '1px solid var(--border-color)' }}>
                  <th style={{ padding: '8px 0', color: 'var(--text-secondary)', fontSize: '0.8rem', fontWeight: 600 }}>Lead</th>
                  <th style={{ padding: '8px 0', color: 'var(--text-secondary)', fontSize: '0.8rem', fontWeight: 600 }}>Interest</th>
                  <th style={{ padding: '8px 0', color: 'var(--text-secondary)', fontSize: '0.8rem', fontWeight: 600 }}>Status</th>
                  <th style={{ padding: '8px 0', color: 'var(--text-secondary)', fontSize: '0.8rem', fontWeight: 600, textAlign: 'right' }}>Action</th>
                </tr>
              </thead>
              <tbody>
                {leads.slice(0, 4).map((lead, i) => (
                  <tr key={lead.id} style={{ borderBottom: i === 3 ? 'none' : '1px solid var(--border-color)' }}>
                    <td style={{ padding: '12px 0' }}>
                      <div style={{ fontWeight: 500, color: 'var(--text-primary)', fontSize: '0.9rem' }}>{lead.name}</div>
                      <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', marginTop: '2px' }}>{lead.phone}</div>
                    </td>
                    <td style={{ padding: '12px 0', color: 'var(--text-primary)', fontSize: '0.9rem' }}>{lead.interest}</td>
                    <td style={{ padding: '12px 0' }}>
                      <span style={{ 
                        padding: '2px 8px', 
                        borderRadius: '3px', 
                        fontSize: '0.75rem', 
                        background: 'var(--bg-app)',
                        color: 'var(--text-secondary)',
                        border: '1px solid var(--border-color)'
                      }}>
                        {lead.status}
                      </span>
                    </td>
                    <td style={{ padding: '12px 0', textAlign: 'right' }}>
                      <button
                        onClick={() => onCallLead(lead)}
                        style={{
                          background: 'var(--primary)',
                          border: 'none',
                          color: 'white',
                          padding: '6px 12px',
                          borderRadius: '3px',
                          display: 'inline-flex', alignItems: 'center', gap: '6px',
                          cursor: 'pointer',
                          fontSize: '0.8rem'
                        }}
                        title={`Call ${lead.name} using AI`}
                      >
                        <PhoneCall size={14} />
                        Call
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* CALL ANALYTICS PANEL */}
        <div style={{ background: 'var(--bg-surface)', borderRadius: '4px', border: '1px solid var(--border-color)', boxShadow: '0 1px 2px rgba(0,0,0,0.05)', display: 'flex', flexDirection: 'column' }}>
          <div style={{ padding: '16px 20px', borderBottom: '1px solid var(--border-color)' }}>
            <h3 style={{ margin: 0, fontSize: '1rem', fontWeight: 600, color: 'var(--text-primary)' }}>AI Call Feed</h3>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', padding: '16px 20px', gap: '16px' }}>
            {callLogs.slice(0, 4).map(log => (
              <div
                key={log.id}
                style={{
                  paddingBottom: '12px',
                  borderBottom: '1px solid var(--border-color)',
                  display: 'flex', flexDirection: 'column', gap: '4px'
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <div style={{ fontWeight: 500, fontSize: '0.9rem', color: 'var(--primary)' }}>{log.leadName}</div>
                  <div style={{ color: 'var(--text-secondary)', fontSize: '0.75rem' }}>{log.duration}</div>
                </div>
                <p style={{ fontSize: '0.85rem', color: 'var(--text-primary)', margin: 0, display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical', overflow: 'hidden' }}>
                  {log.summary}
                </p>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
