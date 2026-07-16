import { useState, useEffect, useCallback } from 'react';
import { PhoneCall, Plus, Trash2, History } from 'lucide-react';
import type { Lead } from '../types';
import { HistoryModal } from './HistoryModal';

interface LeadsTabProps {
  currentUser: { user_id: string; business_name: string };
  searchQuery: string;
  refreshTrigger: number;
  onCallLead: (lead: Lead) => void;
}

export function LeadsTab({ 
  currentUser, 
  searchQuery, 
  refreshTrigger,
  onCallLead
}: LeadsTabProps) {
  const [leads, setLeads] = useState<Lead[]>([]);
  const [showAddLeadForm, setShowAddLeadForm] = useState(false);
  const [newName, setNewName] = useState('');
  const [newPhone, setNewPhone] = useState('');
  const [newInterest, setNewInterest] = useState('');
  const [properties, setProperties] = useState<{ id: number, heading: string }[]>([]);
  const [historyLead, setHistoryLead] = useState<Lead | null>(null);
  const [toastMessage, setToastMessage] = useState<string | null>(null);

  const API_BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

  // Fetch leads from database via FastAPI
  const loadLeads = useCallback(async () => {
    if (!currentUser) return;
    try {
      const response = await fetch(`${API_BASE_URL}/api/leads?user_id=${currentUser.user_id}`);
      if (response.ok) {
        const data = await response.json();
        const mapped = data.map((item: any) => ({
          id: item.lead_id,
          name: item.lead_name,
          phone: item.phone_number,
          status: item.status,
          interest: item.interest,
          date: item.created_at ? item.created_at.substring(0, 10) : "N/A"
        }));
        setLeads(mapped);
      }
    } catch (error) {
      console.error("Failed to load leads:", error);
    }

    try {
      const propResponse = await fetch(`${API_BASE_URL}/api/properties?user_id=${currentUser.user_id}`);
      if (propResponse.ok) {
        const propData = await propResponse.json();
        const mappedProps = propData.map((p: any) => ({
          id: p.id,
          heading: p.property_heading || `Property #${p.id}`
        }));
        setProperties(mappedProps);
        if (mappedProps.length > 0 && !newInterest) {
          setNewInterest(mappedProps[0].heading);
        }
      }
    } catch (error) {
      console.error("Failed to load properties for leads tab:", error);
    }
  }, [currentUser, newInterest]);

  useEffect(() => {
    loadLeads();
  }, [loadLeads, refreshTrigger]);

  // Lead addition handler
  const handleAddLead = async (name: string, phone: string, interest: string) => {
    if (!currentUser) return;
    try {
      const response = await fetch(`${API_BASE_URL}/api/leads`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          lead_name: name,
          phone_number: phone,
          status: "New",
          interest: interest,
          user_id: currentUser.user_id
        })
      });
      if (response.ok) {
        const data = await response.json();
        if (data.warning) {
          setToastMessage(data.warning);
          setTimeout(() => setToastMessage(null), 7000); // Hide after 7 seconds
        }
        await loadLeads();
      } else {
        alert("Failed to save lead to database.");
      }
    } catch (error) {
      console.error("Error adding lead:", error);
    }
  };

  // Lead deletion handler
  const handleDeleteLead = async (leadId: number) => {
    if (confirm("Are you sure you want to remove this lead?")) {
      try {
        const response = await fetch(`${API_BASE_URL}/api/leads/${leadId}`, {
          method: "DELETE"
        });
        if (response.ok) {
          await loadLeads();
        } else {
          alert("Failed to delete lead from database.");
        }
      } catch (error) {
        console.error("Error deleting lead:", error);
      }
    }
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!newName.trim() || !newPhone.trim()) {
      alert("Please fill in both name and phone number.");
      return;
    }
    handleAddLead(newName, newPhone, newInterest);
    setNewName('');
    setNewPhone('');
    if (properties.length > 0) {
      setNewInterest(properties[0].heading);
    } else {
      setNewInterest('');
    }
    setShowAddLeadForm(false);
  };

  // Deprecated handleInitiateCall logic:
  // Instead of calling the API directly here, we use onCallLead to open the DialerModal
  // where the call is initiated and the live transcript is shown.

  const filteredLeads = leads.filter(l =>
    l.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
    l.phone.includes(searchQuery) ||
    l.interest.toLowerCase().includes(searchQuery.toLowerCase())
  );

  return (
    <div>
      <div className="properties-header-actions" style={{ marginBottom: '20px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <h3 style={{ fontSize: '1.25rem', fontWeight: 600 }}>Total Leads Registry</h3>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.85rem' }}>
            Manage lead contacts, requirements, and trigger AI voice calls.
          </p>
        </div>

        <button
          className="btn-add-property"
          onClick={() => setShowAddLeadForm(prev => !prev)}
          style={{ display: 'flex', alignItems: 'center', gap: '8px' }}
        >
          <Plus size={18} />
          <span>{showAddLeadForm ? 'Cancel Editor' : 'Add Lead'}</span>
        </button>
      </div>

      {/* Add Lead Form */}
      {showAddLeadForm && (
        <div className="add-property-section" style={{ marginBottom: '24px', background: 'var(--panel-bg)', padding: '24px', borderRadius: '12px', border: '1px solid var(--border-color)' }}>
          <form onSubmit={handleSubmit} className="add-property-form" style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            <h4 style={{ fontWeight: 600, margin: 0 }}>Register New Lead</h4>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
              <div className="form-group">
                <label style={{ display: 'block', fontSize: '0.85rem', color: 'var(--text-secondary)', marginBottom: '6px' }}>Full Name</label>
                <input
                  type="text"
                  className="form-control"
                  placeholder="e.g. Vikram Malhotra"
                  value={newName}
                  onChange={(e) => setNewName(e.target.value)}
                  required
                />
              </div>

              <div className="form-group">
                <label style={{ display: 'block', fontSize: '0.85rem', color: 'var(--text-secondary)', marginBottom: '6px' }}>Phone Number</label>
                <input
                  type="text"
                  className="form-control"
                  placeholder="e.g. +91 98765 43210"
                  value={newPhone}
                  onChange={(e) => setNewPhone(e.target.value)}
                  required
                />
              </div>
            </div>

            <div className="form-group">
              <label style={{ display: 'block', fontSize: '0.85rem', color: 'var(--text-secondary)', marginBottom: '6px' }}>Interest / Requirements</label>
              <select
                className="form-control"
                value={newInterest}
                onChange={(e) => setNewInterest(e.target.value)}
                style={{ background: 'var(--border-color)', color: 'var(--text-primary)', border: '1px solid var(--border-color)', padding: '10px', borderRadius: '6px', width: '100%' }}
                required
              >
                <option value="" disabled>Select a Property Interest</option>
                {properties.map((prop) => (
                  <option key={prop.id} value={prop.heading}>
                    {prop.heading}
                  </option>
                ))}
              </select>
            </div>

            <div className="form-buttons" style={{ display: 'flex', gap: '12px', justifyContent: 'flex-end', marginTop: '8px' }}>
              <button
                type="button"
                className="btn-cancel"
                onClick={() => setShowAddLeadForm(false)}
              >
                Cancel
              </button>
              <button type="submit" className="btn-submit">
                Register Lead
              </button>
            </div>
          </form>
        </div>
      )}

      {/* History Modal Overlay */}
      {historyLead && (
        <HistoryModal 
          lead={historyLead} 
          onClose={() => setHistoryLead(null)} 
        />
      )}

      {/* Leads Table panel */}
      <div className="section-panel" style={{ background: 'var(--panel-bg)', borderRadius: '12px', border: '1px solid var(--border-color)', overflow: 'hidden' }}>
        <div className="crm-table-container">
          <table className="crm-table">
            <thead>
              <tr>
                <th>ID</th>
                <th>Full Name</th>
                <th>Phone Number</th>
                <th>Interest / Requirements</th>
                <th>Date Registered</th>
                <th>Status Badge</th>
                <th style={{ textAlign: 'center', width: '120px' }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {filteredLeads.length > 0 ? (
                filteredLeads.map((lead) => (
                  <tr key={lead.id}>
                    <td>#{lead.id}</td>
                    <td style={{ fontWeight: 600 }}>{lead.name}</td>
                    <td>{lead.phone}</td>
                    <td>{lead.interest}</td>
                    <td>{lead.date}</td>
                    <td>
                      <span className={`badge ${lead.status.toLowerCase().replace(/\s+/g, '_')}`}>
                        {lead.status}
                      </span>
                    </td>
                    <td>
                      <div style={{ display: 'flex', gap: '8px', justifyContent: 'center' }}>
                        <button
                          className="action-btn call-btn"
                          onClick={() => onCallLead(lead)}
                          title="Start AI voice conversation"
                          style={{
                            display: 'inline-flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            width: '32px',
                            height: '32px',
                            borderRadius: '6px',
                            background: 'rgba(167, 139, 250, 0.1)',
                            color: '#a78bfa',
                            border: 'none',
                            cursor: 'pointer'
                          }}
                        >
                          <PhoneCall size={14} />
                        </button>
                        <button
                          className="action-btn history-btn"
                          onClick={() => setHistoryLead(lead)}
                          title="View past conversation history"
                          style={{
                            display: 'inline-flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            width: '32px',
                            height: '32px',
                            borderRadius: '6px',
                            background: 'rgba(59, 130, 246, 0.1)',
                            color: '#3b82f6',
                            border: 'none',
                            cursor: 'pointer'
                          }}
                        >
                          <History size={14} />
                        </button>
                        <button
                          className="action-btn delete-btn"
                          onClick={() => handleDeleteLead(lead.id)}
                          title="Remove lead"
                          style={{
                            display: 'inline-flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            width: '32px',
                            height: '32px',
                            borderRadius: '6px',
                            background: 'rgba(239, 68, 68, 0.1)',
                            color: '#ef4444',
                            border: 'none',
                            cursor: 'pointer'
                          }}
                        >
                          <Trash2 size={14} />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={7} style={{ textAlign: 'center', color: 'var(--text-secondary)', padding: '24px' }}>
                    No leads matched query.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Custom Bottom Toast Notification */}
      {toastMessage && (
        <div style={{
          position: 'fixed',
          bottom: '24px',
          right: '24px',
          background: '#ffffff',
          color: '#000000',
          padding: '16px 24px',
          borderRadius: '8px',
          boxShadow: '0 4px 12px rgba(0,0,0,0.15)',
          border: '1px solid #e2e8f0',
          borderLeft: '4px solid #f59e0b',
          zIndex: 9999,
          animation: 'slideIn 0.3s ease-out',
          display: 'flex',
          alignItems: 'center',
          gap: '12px'
        }}>
          <div style={{ width: '20px', height: '20px', borderRadius: '50%', background: '#f59e0b', color: '#fff', display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 'bold', fontSize: '14px' }}>!</div>
          <span style={{ fontSize: '0.9rem', fontWeight: 500 }}>{toastMessage}</span>
          <button 
            onClick={() => setToastMessage(null)} 
            style={{ background: 'transparent', border: 'none', color: '#64748b', cursor: 'pointer', marginLeft: '12px', fontSize: '1.2rem' }}
          >
            &times;
          </button>
        </div>
      )}
    </div>
  );
}
