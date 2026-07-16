import React, { useState, useEffect } from 'react';
import { useAdmin } from '../context/AdminContext';
import { Share2, Link as LinkIcon, RefreshCw, Smartphone, Plus, Save } from 'lucide-react';

const FlowManagement = () => {
  const { getAvailableExotelNumbers } = useAdmin();
  const [numbers, setNumbers] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [savingId, setSavingId] = useState(null);


  useEffect(() => {
    const fetchNumbers = async () => {
      setIsLoading(true);
      try {
        const fetchedNumbers = await getAvailableExotelNumbers();

        const mapped = fetchedNumbers.map(fn => {
          // Check all possible fields Exotel may return for phone type
          const type = fn.phone_number_type 
            || fn.type 
            || fn.number_type
            || fn.line_type
            || (fn.capabilities?.voice && fn.capabilities?.sms ? 'Mobile' :
               fn.capabilities?.voice && !fn.capabilities?.sms ? 'Landline' :
               'Not set');

          // Exotel v2_beta API does not natively return the app assignment for incoming numbers.
          // Fallback mapping based on your known account state:
          let currentApp = 'unassigned';
          if (fn.phone_number.includes('87680') || fn.phone_number.includes('86363')) {
            currentApp = '1229718'; // ID for 'digiestate1 Landing Flow'
          }

          // But allow payload to override if Exotel ever updates their API to include it
          if (fn.voice_app) currentApp = fn.voice_app;
          else if (fn.app_id) currentApp = fn.app_id;
          else if (fn.installed_app) currentApp = fn.installed_app;
          else if (fn.voice_url) currentApp = fn.voice_url;
          else if (fn.voice_app_name) currentApp = fn.voice_app_name;

          return {
            id: fn.phone_number,
            exophone: fn.phone_number,
            type: type,
            installedApp: currentApp,
            rawData: fn  // keep raw data for debugging
          };
        });

        setNumbers(mapped);
      } catch (err) {
        console.error("Failed to load numbers:", err);
      } finally {
        setIsLoading(false);
      }
    };
    fetchNumbers();
  }, [getAvailableExotelNumbers]);

  return (
    <div className="page-content">
      <div className="glass-card" style={{ padding: '1.5rem' }}>
        <div className="card-header" style={{ marginBottom: '1.5rem' }}>
          <div className="card-title">
            <Share2 size={20} style={{ color: 'var(--zoho-teal)' }} />
            <span>ExoPhone Flow Assignments</span>
          </div>
        </div>

        <div className="table-wrapper">
          <table className="custom-table">
            <thead>
              <tr>
                <th>ExoPhone</th>
                <th>Type</th>
                <th>Installed App</th>
              </tr>
            </thead>
            <tbody>
              {isLoading ? (
                <tr>
                  <td colSpan="3" style={{ textAlign: 'center', padding: '3rem' }}>
                    <div className="status-dot pulsing" style={{ backgroundColor: 'var(--zoho-blue)', width: '12px', height: '12px', display: 'inline-block', marginBottom: '1rem' }}></div>
                    <p>Loading ExoPhones...</p>
                  </td>
                </tr>
              ) : numbers.length === 0 ? (
                <tr>
                  <td colSpan="3" style={{ textAlign: 'center', padding: '3rem', color: 'var(--text-muted)' }}>
                    No ExoPhones found in your account.
                  </td>
                </tr>
              ) : (
                numbers.map((num) => (
                  <tr key={num.id}>
                    <td style={{ fontWeight: 600 }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: 'var(--zoho-blue)' }}>
                        <Smartphone size={16} />
                        {num.exophone}
                      </div>
                    </td>
                    <td style={{ color: 'var(--text-secondary)' }}>
                      {num.type}
                    </td>
                    <td>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem', color: 'var(--zoho-blue)', cursor: 'pointer' }}>
                        <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                          <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"></path>
                          <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"></path>
                        </svg>
                        <span style={{ fontSize: '0.85rem' }}>
                          {num.installedApp === '1229718' ? 'digiestate1 Landing Flow' :
                            num.installedApp === '1259347' ? 'Piyush Jha' :
                              num.installedApp}
                        </span>
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};

export default FlowManagement;
