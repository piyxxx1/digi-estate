import React from 'react';
import { NavLink } from 'react-router-dom';
import { LayoutDashboard, UserCheck, History, Sliders, PhoneCall, Bot, LayoutGrid, Phone } from 'lucide-react';

const Sidebar = () => {
  return (
    <aside className="sidebar">
      <div className="sidebar-logo">
        <div className="logo-icon-wrapper">
          <LayoutGrid size={18} />
        </div>
        <h1 className="sidebar-text">AI Caller <span style={{ color: 'var(--zoho-blue)' }}>Admin</span></h1>
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
