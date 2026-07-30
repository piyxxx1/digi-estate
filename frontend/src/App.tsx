import { useState } from 'react';
import { Routes, Route } from 'react-router-dom';
import { Sidebar } from './components/Sidebar';
import { Header } from './components/Header';
import { DashboardTab } from './components/DashboardTab';
import { PropertiesTab } from './components/PropertiesTab';
import { LeadsTab } from './components/LeadsTab';
import { CallsTab } from './components/CallsTab';
import { DialerModal } from './components/DialerModal';
import { Login } from './components/Login';
import { ProfileTab } from './components/ProfileTab';
import { LandingPage } from './components/LandingPage';
import type { Lead } from './types';
import './App.css';

function App() {
  const [currentUser, setCurrentUser] = useState<{ user_id: string; business_name: string } | null>(() => {
    const savedUser = localStorage.getItem('user');
    return savedUser ? JSON.parse(savedUser) : null;
  });
  const [showLogin, setShowLogin] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');

  // Dialer popup modal state
  const [showCallModal, setShowCallModal] = useState(false);
  const [activeCallLead, setActiveCallLead] = useState<Lead | null>(null);

  // Global coordination trigger to refresh statistics across tabs when database changes
  const [refreshTrigger, setRefreshTrigger] = useState(0);

  const handleCallLead = (lead: Lead) => {
    setActiveCallLead(lead);
    setShowCallModal(true);
  };

  const handleCloseCallModal = (didUpdate?: boolean) => {
    setShowCallModal(false);
    if (didUpdate) {
      setRefreshTrigger(prev => prev + 1);
    }
  };

  if (!currentUser) {
    if (showLogin) {
      return <Login onLogin={setCurrentUser} onBackToLanding={() => setShowLogin(false)} />;
    }
    return <LandingPage onEnterCRM={() => setShowLogin(true)} />;
  }

  return (
    <div className="crm-container">
      {/* Sidebar Navigation */}
      <Sidebar
        businessName={currentUser.business_name}
        onLogout={() => {
          localStorage.removeItem('access_token');
          localStorage.removeItem('refresh_token');
          localStorage.removeItem('user');
          setCurrentUser(null);
        }}
      />

      {/* Main CRM area */}
      <main className="crm-main">
        {/* Header Bar */}
        <Header searchQuery={searchQuery} setSearchQuery={setSearchQuery} />

        {/* Content Viewport */}
        <div className="crm-content">
          <Routes>
            <Route
              path="/"
              element={
                <DashboardTab
                  currentUser={currentUser}
                  refreshTrigger={refreshTrigger}
                  onCallLead={handleCallLead}
                />
              }
            />
            <Route
              path="/properties"
              element={
                <PropertiesTab
                  currentUser={currentUser}
                  searchQuery={searchQuery}
                  refreshTrigger={refreshTrigger}
                />
              }
            />
            <Route
              path="/leads"
              element={
                <LeadsTab
                  currentUser={currentUser}
                  searchQuery={searchQuery}
                  refreshTrigger={refreshTrigger}
                  onCallLead={handleCallLead}
                />
              }
            />
            <Route
              path="/calls"
              element={
                <CallsTab
                  currentUser={currentUser}
                  searchQuery={searchQuery}
                  refreshTrigger={refreshTrigger}
                />
              }
            />
            <Route
              path="/profile"
              element={<ProfileTab currentUser={currentUser} />}
            />
          </Routes>
        </div>
      </main>

      {/* Dialer Overlay Modal */}
      {showCallModal && activeCallLead && (
        <DialerModal
          activeCallLead={activeCallLead}
          onClose={handleCloseCallModal}
        />
      )}
    </div>
  );
}

export default App;
