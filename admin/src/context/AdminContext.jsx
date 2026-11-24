import React, { createContext, useContext } from 'react';
import { useMetrics } from '../hooks/useMetrics';
import { useAgents } from '../hooks/useAgents';
import { useCrmUsers } from '../hooks/useCrmUsers';
import { useLeads } from '../hooks/useLeads';
import { useCalls } from '../hooks/useCalls';

const AdminContext = createContext();

export const useAdmin = () => {
  const context = useContext(AdminContext);
  if (!context) {
    throw new Error('useAdmin must be used within an AdminProvider');
  }
  return context;
};

export const AdminProvider = ({ children }) => {
  const { metrics, setMetrics, companyUsage, telemetryRaw, isLoadingTelemetry, refreshTelemetry } = useMetrics();
  const { agents, updateAgent } = useAgents();
  const { 
    crmUsers, 
    addCrmUser, 
    deleteCrmUser, 
    updateCrmUser, 
    getAvailableExotelNumbers
  } = useCrmUsers();
  
  const { leads, setLeads, addLead, deleteLead, assignLeads } = useLeads();
  
  const { calls, triggerCall, isLoadingCalls } = useCalls({
    crmUsers, 
    leads, 
    setLeads, 
    setMetrics
  });

  return (
    <AdminContext.Provider value={{
      metrics, setMetrics,
      companyUsage, telemetryRaw, isLoadingTelemetry, refreshTelemetry,
      crmUsers, addCrmUser, deleteCrmUser, updateCrmUser,
      leads, setLeads, addLead, deleteLead, assignLeads,
      calls, triggerCall, isLoadingCalls,
      agents,
      updateAgent,
      getAvailableExotelNumbers
    }}>
      {children}
    </AdminContext.Provider>
  );
};
