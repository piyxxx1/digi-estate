import React from 'react';
import { NavLink } from 'react-router-dom';
import { LayoutDashboard, UserCheck, History, Sliders, PhoneCall, Bot, LayoutGrid, Phone } from 'lucide-react';

const Sidebar = () => {
  return (
    <aside className="sidebar">
      <div className="sidebar-logo" style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
        <img 
          src="/logo.webp" 
          alt="Digital Estate Logo" 
          style={{ width: '36px', height: '36px', objectFit: 'contain' }}
        />
        <div style={{ display: 'flex', flexDirection: 'column' }}>
          <h1 className="sidebar-text" style={{ margin: 0, fontSize: '1.05rem', fontWeight: 700, lineHeight: 1.2 }}>
            Digital Estate <span style={{ color: 'var(--zoho-blue)' }}>Admin</span>
          </h1>
          <span style={{ fontSize: '0.72rem', color: 'var(--text-muted, #9ca3af)', letterSpacing: '0.5px' }}>Management Suite</span>
        </div>
      </div>

      <nav className="sidebar-nav">
        <NavLink 
          to="/" 
          className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}
          end
        >
          <LayoutDashboard size={18} />
          <span className="sidebar-text">Dashboard</span>
        </NavLink>

        <NavLink 
          to="/assignment" 
          className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}
        >
          <UserCheck size={18} />
          <span className="sidebar-text">User Assignment</span>
        </NavLink>

        <NavLink 
          to="/logs" 
          className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}
        >
          <History size={18} />
          <span className="sidebar-text">Call History</span>
        </NavLink>

        <NavLink 
          to="/flows" 
          className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}
        >
          <PhoneCall size={18} />
          <span className="sidebar-text">Flow Management</span>
        </NavLink>

        <NavLink 
          to="/exophones" 
          className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}
        >
          <Phone size={18} />
          <span className="sidebar-text">ExoPhones</span>
        </NavLink>
      </nav>

      <div className="sidebar-footer">
        <div className="user-avatar">AD</div>
        <div className="user-info sidebar-text">
          <span className="user-name">Admin Director</span>
          <span className="user-role">System Design Tech</span>
        </div>
      </div>
    </aside>
  );
};

export default Sidebar;
