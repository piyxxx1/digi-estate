import { useState } from 'react';

export const useAgents = () => {
  const [agents, setAgents] = useState([
    { id: 'agent-1', name: 'Sales Pro (Sarah)', role: 'Lead Qualification', voice: 'en-US-Neural-A', prompt: 'You are Sarah, a helpful sales representative...', activeCalls: 1 },
    { id: 'agent-2', name: 'Billing Support (Mike)', role: 'Account & Billing Support', voice: 'en-US-Neural-B', prompt: 'You are Mike, handling billing inquiries...', activeCalls: 1 },
    { id: 'agent-3', name: 'Follow-up Assistant (Alex)', role: 'Callback & Retargeting', voice: 'en-GB-Neural-A', prompt: 'You are Alex, following up on recent interests...', activeCalls: 1 },
    { id: 'agent-4', name: 'Customer Care (Emma)', role: 'General Inquiries', voice: 'en-AU-Neural-A', prompt: 'You are Emma, providing customer care...', activeCalls: 0 },
  ]);

  // Action: Update agent prompt/configuration
  const updateAgent = (agentId, updatedFields) => {
    setAgents(prev => prev.map(agent => {
      if (agent.id === agentId) {
        return { ...agent, ...updatedFields };
      }
      return agent;
    }));
  };

  return { agents, setAgents, updateAgent };
};
