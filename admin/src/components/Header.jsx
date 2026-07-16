import React from 'react';
import { useLocation } from 'react-router-dom';
import { useAdmin } from '../context/AdminContext';
import { ShieldCheck, PhoneOutgoing, Cpu, Search, Bell, HelpCircle, Settings } from 'lucide-react';

const Header = () => {
  const location = useLocation();
  const { metrics } = useAdmin();

  // Determine headers based on location path
  const getHeaderContext = () => {
    switch (location.pathname) {
      case '/':
        return {
          title: 'System Dashboard',
          subtitle: 'Real-time telemetry and call metrics for the AI Caller system'
        };
      case '/assignment':
        return {
          title: 'User Assignment Board',
          subtitle: 'Manage leads and allocate them to specialized AI personas'
        };
      case '/logs':
        return {
          title: 'Call Auditing & Transcripts',
          subtitle: 'Audit conversation flows, latency breakdowns, and prompt response accuracy'
        };
      case '/flows':
        return {
          title: 'App Flow Management',
          subtitle: 'Manage and connect Exotel Virtual Numbers to AI workflows'
        };
      default:
        return {
          title: 'Admin Console',
          subtitle: 'AI Caller management system'
        };
    }
  };

  const headerInfo = getHeaderContext();

  return (
    <header className="header">
      {/* Title & Subtitle Info */}
      <div className="header-title-section">
        <h2>{headerInfo.title}</h2>
        <p>{headerInfo.subtitle}</p>
      </div>

      {/* Zoho Zia-style Global Search Bar */}
      <div className="header-search-container">
        <Search size={16} />
        <input 
          type="text" 
          placeholder="Search in AI Caller (Zia Search)..." 
          disabled
          style={{ cursor: 'not-allowed' }}
        />
      </div>

      {/* Header telemetry and utility actions */}
      <div className="header-actions">


        {/* Decorative Zoho system icons */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', borderLeft: '1px solid var(--border-color)', paddingLeft: '1rem', color: 'var(--text-muted)' }}>
          <Bell size={18} style={{ cursor: 'pointer' }} title="Notifications" />
          <HelpCircle size={18} style={{ cursor: 'pointer' }} title="Help Center" />
          <Settings size={18} style={{ cursor: 'pointer' }} title="Admin Settings" />
        </div>
      </div>
    </header>
  );
};

export default Header;
