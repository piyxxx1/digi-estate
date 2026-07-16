import React, { useState, useEffect } from 'react';
import { useAdmin } from '../context/AdminContext';
import { Phone, CheckCircle, XCircle, ExternalLink, Info } from 'lucide-react';

const ExoPhones = () => {
  const { crmUsers, getAvailableExotelNumbers } = useAdmin();
  const [exoPhones, setExoPhones] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    const fetchPhones = async () => {
      setIsLoading(true);
      try {
        const numbers = await getAvailableExotelNumbers();
        // Map numbers with their assigned CRM accounts
        const mappedNumbers = numbers.map(num => {
          const assignedUser = crmUsers.find(u => u.virtualNumber === num.phone_number);
          return {
            ...num,
            assignedTo: assignedUser ? assignedUser.businessName : null,
            userId: assignedUser ? assignedUser.id : null,
            status: assignedUser ? 'Assigned' : 'Unassigned'
          };
        });
        setExoPhones(mappedNumbers);
      } catch (err) {
        setError(err.message || 'Failed to fetch ExoPhones.');
      } finally {
        setIsLoading(false);
      }
    };
    fetchPhones();
  }, [crmUsers, getAvailableExotelNumbers]);

  return (
    <div className="page-content">
      <div className="search-filter-bar" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <h2 style={{ fontSize: '1.5rem', fontWeight: 600, color: 'var(--text-main)', margin: 0, marginBottom: '0.25rem' }}>ExoPhones Inventory</h2>
          <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem', margin: 0 }}>Manage Exotel virtual numbers for CRM assignment.</p>
        </div>
      </div>

      <div className="glass-card" style={{ marginTop: '1.5rem' }}>
        <div className="card-header" style={{ marginBottom: '1.25rem' }}>
          <div className="card-title">
            <Phone size={18} style={{ color: 'var(--zoho-blue)' }} />
            <span>Virtual Numbers ({exoPhones.length})</span>
          </div>
        </div>

        {isLoading ? (
          <div style={{ textAlign: 'center', padding: '3rem' }}>
            <span className="status-dot pulsing" style={{ backgroundColor: 'var(--zoho-blue)', width: 12, height: 12, display: 'inline-block' }}></span>
            <p style={{ marginTop: '1rem', color: 'var(--text-muted)' }}>Loading ExoPhones from Exotel API...</p>
          </div>
        ) : error ? (
          <div style={{ padding: '2rem', textAlign: 'center', color: 'var(--zoho-red)' }}>
            <p>Error loading numbers: {error}</p>
          </div>
        ) : (
          <div className="table-wrapper">
            <table className="custom-table">
              <thead>
                <tr>
                  <th>Phone Number</th>
                  <th>Friendly Name</th>
                  <th>Assignment Status</th>
                  <th>Assigned Business</th>
                  <th>Flow Setup</th>
                </tr>
              </thead>
              <tbody>
                {exoPhones.length === 0 ? (
                  <tr>
                    <td colSpan="5" style={{ textAlign: 'center', padding: '2rem', color: 'var(--text-muted)' }}>
                      No ExoPhones found in your account.
                    </td>
                  </tr>
                ) : (
                  exoPhones.map(phone => (
                    <tr key={phone.phone_number}>
                      <td style={{ fontWeight: 700, fontFamily: 'var(--font-mono)' }}>{phone.phone_number}</td>
                      <td>{phone.friendly_name || '-'}</td>
                      <td>
                        {phone.status === 'Assigned' ? (
                          <span className="badge badge-success" style={{ display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
                            <CheckCircle size={12} /> Assigned
                          </span>
                        ) : (
                          <span className="badge" style={{ background: 'var(--bg-light)', color: 'var(--text-muted)', border: '1px solid var(--border-color)', display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
                            <XCircle size={12} /> Unassigned
                          </span>
                        )}
                      </td>
                      <td style={{ fontWeight: 500, color: phone.assignedTo ? 'var(--text-main)' : 'var(--text-muted)' }}>
                        {phone.assignedTo || 'Available for assignment'}
                        {phone.userId && <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', fontWeight: 400 }}>{phone.userId}</div>}
                      </td>
                      <td>
                        {phone.voice_url ? (
                          <a 
                            href={phone.voice_url} 
                            target="_blank" 
                            rel="noopener noreferrer"
                            style={{ fontSize: '0.8rem', color: 'var(--zoho-blue)', textDecoration: 'none', display: 'inline-flex', alignItems: 'center', gap: '4px' }}
                          >
                            View Exotel App <ExternalLink size={12} />
                          </a>
                        ) : (
                          <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>Not configured</span>
                        )}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        )}
        
        <div style={{ marginTop: '1.5rem', padding: '1rem', background: 'var(--bg-light)', borderRadius: '8px', display: 'flex', gap: '1rem', alignItems: 'flex-start' }}>
          <Info size={20} style={{ color: 'var(--zoho-blue)', flexShrink: 0 }} />
          <div style={{ fontSize: '0.85rem', color: 'var(--text-muted)', lineHeight: '1.5' }}>
            <strong>Number Inventory:</strong> These virtual numbers are provisioned directly from the Exotel dashboard. They are automatically synced here and available for assignment to CRM users in the User Assignment tab.
          </div>
        </div>
      </div>
    </div>
  );
};

export default ExoPhones;
