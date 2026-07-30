import { NavLink } from 'react-router-dom';
import { LayoutDashboard, Briefcase, Users, PhoneCall, UserCircle, LogOut } from 'lucide-react';

interface SidebarProps {
  businessName?: string;
  onLogout?: () => void;
}

export function Sidebar({ businessName, onLogout }: SidebarProps) {
  // Generate a 2-letter avatar from business name or default
  const getAvatarInitials = (name?: string) => {
    if (!name) return "AD";
    const words = name.split(' ');
    if (words.length >= 2) return (words[0][0] + words[1][0]).toUpperCase();
    return name.substring(0, 2).toUpperCase();
  };

  return (
    <aside className="crm-sidebar">
      <div className="crm-sidebar-logo">
        <PhoneCall className="crm-logo-icon" />
        <h1>DigiCRM</h1>
      </div>

      <nav className="crm-menu">
        <NavLink
          to="/"
          className={({ isActive }) => `crm-menu-item ${isActive ? 'active' : ''}`}
          end
        >
          <LayoutDashboard size={18} />
          <span>Dashboard</span>
        </NavLink>

        <NavLink
          to="/properties"
          className={({ isActive }) => `crm-menu-item ${isActive ? 'active' : ''}`}
        >
          <Briefcase size={18} />
          <span>Products & Listings</span>
        </NavLink>

        <NavLink
          to="/leads"
          className={({ isActive }) => `crm-menu-item ${isActive ? 'active' : ''}`}
        >
          <Users size={18} />
          <span>Leads Portfolio</span>
        </NavLink>

        <NavLink
          to="/calls"
          className={({ isActive }) => `crm-menu-item ${isActive ? 'active' : ''}`}
        >
          <PhoneCall size={18} />
          <span>Voice Logs</span>
        </NavLink>

        <NavLink
          to="/profile"
          className={({ isActive }) => `crm-menu-item ${isActive ? 'active' : ''}`}
        >
          <UserCircle size={18} />
          <span>My Profile</span>
        </NavLink>
      </nav>

      <div className="crm-sidebar-footer">
        <div className="crm-user-profile">
          <div className="crm-user-avatar">{getAvatarInitials(businessName)}</div>
          <div className="crm-user-info">
            <span className="crm-user-name">{businessName || "Admin Director"}</span>
            <span className="crm-user-role">Estate Manager</span>
          </div>
          <div style={{ marginLeft: 'auto', display: 'flex', gap: '8px', alignItems: 'center' }}>
            <NavLink to="/profile" style={{ display: 'flex', alignItems: 'center', color: '#fff' }}>
              <UserCircle size={16} style={{ color: '#fff', cursor: 'pointer', opacity: 0.85 }} />
            </NavLink>
            <LogOut size={16} style={{ color: '#fff', cursor: 'pointer', opacity: 0.85 }} onClick={onLogout} />
          </div>
        </div>
      </div>
    </aside>
  );
}
