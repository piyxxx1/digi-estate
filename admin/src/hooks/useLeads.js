import { useState } from 'react';

export const useLeads = () => {
  const [leads, setLeads] = useState([
    { id: 1, name: 'John Doe', phone: '+1 (555) 019-2834', email: 'john.doe@gmail.com', status: 'Pending', assignedAgent: 'Sales Pro (Sarah)', priority: 'High', lastCallDate: '-' },
    { id: 2, name: 'Alice Smith', phone: '+1 (555) 043-9812', email: 'alice.s@yahoo.com', status: 'Called', assignedAgent: 'Billing Support (Mike)', priority: 'Medium', lastCallDate: '2026-05-30' },
    { id: 3, name: 'Bob Johnson', phone: '+1 (555) 076-4521', email: 'bob.j@outlook.com', status: 'In Progress', assignedAgent: 'Follow-up Assistant (Alex)', priority: 'High', lastCallDate: '2026-05-31' },
    { id: 4, name: 'Emily Davis', phone: '+1 (555) 098-1122', email: 'emily.d@gmail.com', status: 'Pending', assignedAgent: 'Unassigned', priority: 'Low', lastCallDate: '-' },
  ]);

  const addLead = (newLead) => {
    const lead = {
      id: leads.length + 1,
      lastCallDate: '-',
      status: 'Pending',
      ...newLead
    };
    setLeads(prev => [lead, ...prev]);
  };

  const deleteLead = (id) => {
    setLeads(prev => prev.filter(lead => lead.id !== id));
  };

  const assignLeads = (leadIds, agentName) => {
    setLeads(prev => prev.map(lead => {
      if (leadIds.includes(lead.id)) {
        return { ...lead, assignedAgent: agentName };
      }
      return lead;
    }));
  };

  return { leads, setLeads, addLead, deleteLead, assignLeads };
};
