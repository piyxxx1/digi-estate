import { useState, useEffect } from 'react';
import { User, Building2, Phone, Mail, Shield, Clock, Edit2, Save, X } from 'lucide-react';

interface ProfileTabProps {
  currentUser: { user_id: string; business_name: string };
}

interface UserProfile {
  user_id: string;
  business_name: string;
  exotel_virtual_number: string | null;
}

export function ProfileTab({ currentUser }: ProfileTabProps) {
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isEditing, setIsEditing] = useState(false);
  const [editName, setEditName] = useState('');
  const [isSaving, setIsSaving] = useState(false);
  const [saveMsg, setSaveMsg] = useState('');

  const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

  useEffect(() => {
    const fetchProfile = async () => {
      setIsLoading(true);
      try {
        const res = await fetch(`${API_BASE_URL}/api/users`);
        if (res.ok) {
          const data: UserProfile[] = await res.json();
          const me = data.find(u => u.user_id === currentUser.user_id);
          if (me) {
            setProfile(me);
            setEditName(me.business_name);
          }
        }
      } catch (err) {
        console.error('Failed to load profile:', err);
      } finally {
        setIsLoading(false);
      }
    };
    fetchProfile();
  }, [currentUser.user_id, API_BASE_URL]);

  const handleSave = async () => {
    if (!editName.trim()) return;
    setIsSaving(true);
    try {
      const res = await fetch(`${API_BASE_URL}/api/users/${encodeURIComponent(currentUser.user_id)}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ business_name: editName.trim() })
      });
      if (res.ok) {
        const updated = await res.json();
        setProfile(prev => prev ? { ...prev, business_name: updated.business_name } : prev);
        setIsEditing(false);
        setSaveMsg('Profile updated successfully!');
        setTimeout(() => setSaveMsg(''), 3000);
      }
    } catch (err) {
      console.error('Failed to update profile:', err);
    } finally {
      setIsSaving(false);
    }
  };

  const getInitials = (name: string) => {
    const words = name.split(' ');
    if (words.length >= 2) return (words[0][0] + words[1][0]).toUpperCase();
    return name.substring(0, 2).toUpperCase();
  };

  if (isLoading) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: '#888' }}>
        <div style={{ textAlign: 'center' }}>
          <div style={{ width: 40, height: 40, border: '3px solid #2563eb', borderTopColor: 'transparent', borderRadius: '50%', animation: 'spin 0.8s linear infinite', margin: '0 auto 1rem' }} />
          <p>Loading profile...</p>
        </div>
      </div>
    );
  }

  const displayProfile = profile || { user_id: currentUser.user_id, business_name: currentUser.business_name, exotel_virtual_number: null };

  return (
    <div style={{ maxWidth: 720, margin: '0 auto', padding: '2rem 1.5rem' }}>
      {/* Header Banner */}
      <div style={{
        background: 'linear-gradient(135deg, #1e3a5f 0%, #2563eb 60%, #3b82f6 100%)',
        borderRadius: '16px',
        padding: '2.5rem 2rem',
        position: 'relative',
        overflow: 'hidden',
        marginBottom: '1.5rem',
        boxShadow: '0 8px 32px rgba(37,99,235,0.25)'
      }}>
        {/* Decorative circles */}
        <div style={{ position: 'absolute', top: -40, right: -40, width: 200, height: 200, borderRadius: '50%', background: 'rgba(255,255,255,0.05)' }} />
        <div style={{ position: 'absolute', bottom: -60, right: 60, width: 150, height: 150, borderRadius: '50%', background: 'rgba(255,255,255,0.04)' }} />

        <div style={{ display: 'flex', alignItems: 'center', gap: '1.5rem', position: 'relative' }}>
          {/* Avatar */}
          <div style={{
            width: 80, height: 80, borderRadius: '50%',
            background: 'rgba(255,255,255,0.15)',
            backdropFilter: 'blur(8px)',
            border: '3px solid rgba(255,255,255,0.3)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontSize: '1.8rem', fontWeight: 700, color: '#fff',
            flexShrink: 0
          }}>
            {getInitials(displayProfile.business_name)}
          </div>

          <div style={{ flex: 1 }}>
            {isEditing ? (
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.25rem' }}>
                <input
                  value={editName}
                  onChange={e => setEditName(e.target.value)}
                  style={{
                    background: 'rgba(255,255,255,0.15)', border: '1px solid rgba(255,255,255,0.4)',
                    borderRadius: 8, padding: '0.4rem 0.75rem', color: '#fff',
                    fontSize: '1.1rem', fontWeight: 600, outline: 'none', width: 260
                  }}
                  autoFocus
                />
                <button onClick={handleSave} disabled={isSaving} style={{ background: 'rgba(255,255,255,0.2)', border: 'none', borderRadius: 8, padding: '0.4rem 0.75rem', color: '#fff', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 4 }}>
                  <Save size={14} /> {isSaving ? 'Saving…' : 'Save'}
                </button>
                <button onClick={() => setIsEditing(false)} style={{ background: 'transparent', border: 'none', color: 'rgba(255,255,255,0.7)', cursor: 'pointer' }}>
                  <X size={18} />
                </button>
              </div>
            ) : (
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.25rem' }}>
                <h1 style={{ margin: 0, color: '#fff', fontSize: '1.5rem', fontWeight: 700 }}>{displayProfile.business_name}</h1>
                <button onClick={() => setIsEditing(true)} style={{ background: 'rgba(255,255,255,0.15)', border: 'none', borderRadius: 6, padding: '0.25rem 0.5rem', color: 'rgba(255,255,255,0.8)', cursor: 'pointer', display: 'flex', alignItems: 'center' }}>
                  <Edit2 size={13} />
                </button>
              </div>
            )}
            <p style={{ margin: 0, color: 'rgba(255,255,255,0.7)', fontSize: '0.9rem' }}>Operations Manager · DigiCRM</p>
          </div>

          <div style={{ textAlign: 'right' }}>
            <span style={{ background: 'rgba(34,197,94,0.2)', border: '1px solid rgba(34,197,94,0.4)', borderRadius: 20, padding: '0.25rem 0.75rem', color: '#86efac', fontSize: '0.78rem', fontWeight: 600 }}>
              ● Active
            </span>
          </div>
        </div>
      </div>

      {/* Success message */}
      {saveMsg && (
        <div style={{ background: 'rgba(34,197,94,0.1)', border: '1px solid rgba(34,197,94,0.3)', borderRadius: 10, padding: '0.75rem 1rem', color: '#16a34a', marginBottom: '1rem', fontSize: '0.9rem' }}>
          {saveMsg}
        </div>
      )}

      {/* Info Cards */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem', marginBottom: '1rem' }}>

        {/* User ID */}
        <div style={{ background: 'var(--crm-card-bg, #fff)', border: '1px solid var(--crm-border, #e5e7eb)', borderRadius: 12, padding: '1.25rem', boxShadow: '0 1px 6px rgba(0,0,0,0.05)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', marginBottom: '0.75rem' }}>
            <div style={{ width: 36, height: 36, borderRadius: 10, background: 'rgba(37,99,235,0.1)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <Mail size={18} style={{ color: '#2563eb' }} />
            </div>
            <span style={{ fontWeight: 600, fontSize: '0.85rem', color: '#6b7280', textTransform: 'uppercase', letterSpacing: '0.04em' }}>Email / User ID</span>
          </div>
          <p style={{ margin: 0, fontWeight: 600, fontSize: '0.95rem', color: '#111827', wordBreak: 'break-all' }}>{displayProfile.user_id}</p>
          <p style={{ margin: '0.25rem 0 0', fontSize: '0.78rem', color: '#9ca3af' }}>Your unique login credential</p>
        </div>

        {/* Business Name */}
        <div style={{ background: 'var(--crm-card-bg, #fff)', border: '1px solid var(--crm-border, #e5e7eb)', borderRadius: 12, padding: '1.25rem', boxShadow: '0 1px 6px rgba(0,0,0,0.05)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', marginBottom: '0.75rem' }}>
            <div style={{ width: 36, height: 36, borderRadius: 10, background: 'rgba(124,58,237,0.1)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <Building2 size={18} style={{ color: '#7c3aed' }} />
            </div>
            <span style={{ fontWeight: 600, fontSize: '0.85rem', color: '#6b7280', textTransform: 'uppercase', letterSpacing: '0.04em' }}>Business Name</span>
          </div>
          <p style={{ margin: 0, fontWeight: 600, fontSize: '0.95rem', color: '#111827' }}>{displayProfile.business_name}</p>
          <p style={{ margin: '0.25rem 0 0', fontSize: '0.78rem', color: '#9ca3af' }}>Registered organisation</p>
        </div>

        {/* Assigned Virtual Number */}
        <div style={{ background: 'var(--crm-card-bg, #fff)', border: '1px solid var(--crm-border, #e5e7eb)', borderRadius: 12, padding: '1.25rem', boxShadow: '0 1px 6px rgba(0,0,0,0.05)', gridColumn: '1 / -1' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', marginBottom: '0.75rem' }}>
            <div style={{ width: 36, height: 36, borderRadius: 10, background: 'rgba(16,185,129,0.1)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <Phone size={18} style={{ color: '#10b981' }} />
            </div>
            <span style={{ fontWeight: 600, fontSize: '0.85rem', color: '#6b7280', textTransform: 'uppercase', letterSpacing: '0.04em' }}>Assigned AI Phone Number (ExoPhone)</span>
          </div>
          {displayProfile.exotel_virtual_number ? (
            <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
              <p style={{ margin: 0, fontWeight: 700, fontSize: '1.25rem', color: '#111827', fontFamily: 'monospace', letterSpacing: '0.08em' }}>{displayProfile.exotel_virtual_number}</p>
              <span style={{ background: 'rgba(16,185,129,0.1)', border: '1px solid rgba(16,185,129,0.3)', borderRadius: 20, padding: '0.2rem 0.6rem', color: '#059669', fontSize: '0.75rem', fontWeight: 600 }}>
                ● Connected
              </span>
            </div>
          ) : (
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <p style={{ margin: 0, fontWeight: 600, fontSize: '0.95rem', color: '#9ca3af' }}>No number assigned</p>
              <span style={{ background: 'rgba(245,158,11,0.1)', border: '1px solid rgba(245,158,11,0.3)', borderRadius: 20, padding: '0.2rem 0.6rem', color: '#d97706', fontSize: '0.75rem', fontWeight: 600 }}>
                ● Pending
              </span>
            </div>
          )}
          <p style={{ margin: '0.25rem 0 0', fontSize: '0.78rem', color: '#9ca3af' }}>Managed by your administrator via Exotel</p>
        </div>
      </div>

      {/* Account Security row */}
      <div style={{ background: 'var(--crm-card-bg, #fff)', border: '1px solid var(--crm-border, #e5e7eb)', borderRadius: 12, padding: '1.25rem', boxShadow: '0 1px 6px rgba(0,0,0,0.05)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', marginBottom: '0.75rem' }}>
          <div style={{ width: 36, height: 36, borderRadius: 10, background: 'rgba(239,68,68,0.1)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <Shield size={18} style={{ color: '#ef4444' }} />
          </div>
          <span style={{ fontWeight: 600, fontSize: '0.85rem', color: '#6b7280', textTransform: 'uppercase', letterSpacing: '0.04em' }}>Account Security</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', flexWrap: 'wrap' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', fontSize: '0.85rem', color: '#374151' }}>
            <User size={14} style={{ color: '#6b7280' }} />
            <span>Account Type: <strong>CRM User</strong></span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', fontSize: '0.85rem', color: '#374151' }}>
            <Clock size={14} style={{ color: '#6b7280' }} />
            <span>Session: <strong>Active</strong></span>
          </div>
          <p style={{ margin: 0, fontSize: '0.78rem', color: '#9ca3af', width: '100%' }}>
            To change your password or request a new ExoPhone number, contact your administrator.
          </p>
        </div>
      </div>
    </div>
  );
}
