import React from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { AdminProvider } from './context/AdminContext';
import Sidebar from './components/Sidebar';
import Header from './components/Header';
import Dashboard from './pages/Dashboard';
import UserAssignment from './pages/UserAssignment';
import CallLogs from './pages/CallLogs';
import FlowManagement from './pages/FlowManagement';
import ExoPhones from './pages/ExoPhones';
import './App.css';

function App() {
  return (
    <AdminProvider>
      <BrowserRouter>
        <div className="app-container">
          {/* Left panel sidebar navigation */}
          <Sidebar />

          {/* Right panel layout container */}
          <div className="main-panel">
            {/* Context-aware top header */}
            <Header />

            {/* Application pages routes */}
            <Routes>
              <Route path="/" element={<Dashboard />} />
              <Route path="/assignment" element={<UserAssignment />} />
              <Route path="/logs" element={<CallLogs />} />
              <Route path="/flows" element={<FlowManagement />} />
              <Route path="/exophones" element={<ExoPhones />} />
            </Routes>
          </div>
        </div>
      </BrowserRouter>
    </AdminProvider>
  );
}

export default App;
