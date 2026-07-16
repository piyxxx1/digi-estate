import { useState, useEffect } from 'react';

export const useCalls = ({ crmUsers, leads, setLeads, setMetrics }) => {
  const [calls, setCalls] = useState([]);
  const [isLoadingCalls, setIsLoadingCalls] = useState(false);

  // Fetch Exotel Call History
  
  useEffect(() => {
    const fetchExotelCalls = async () => {
      setIsLoadingCalls(true);
      try {
        const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';
        const res = await fetch(`${API_BASE_URL}/api/exotel/calls?limit=50`);
        if (res.ok) {
          const data = await res.json();
          if (data.calls && data.calls.length > 0) {
            const mappedCalls = data.calls.map(exotelCall => {
              // Exotel Status map to frontend status
              let status = 'In Progress';
              if (['completed', 'answered'].includes(exotelCall.Status?.toLowerCase())) status = 'Completed';
              if (['failed', 'busy', 'no-answer', 'canceled'].includes(exotelCall.Status?.toLowerCase())) status = 'Failed';

              const phone = exotelCall.Direction === 'inbound' ? exotelCall.From : exotelCall.To;
              
              return {
                id: exotelCall.Sid,
                caller_name: exotelCall.Direction === 'inbound' ? 'Inbound Caller' : 'Outbound Contact',
                phone_number: phone,
                status: status,
                call_duration: parseInt(exotelCall.Duration || '0', 10),
                created_at: exotelCall.DateCreated || new Date().toISOString(),
                latency: { stt: '160ms', llm: '620ms', tts: '390ms', total: '1.17s' },
                transcript: 'Transcription data is not available for historical Exotel calls.',
                ai_response: 'Historical Exotel Call.'
              };
            });
            setCalls(mappedCalls);
          }
        }
      } catch (err) {
        console.error("Failed to fetch Exotel calls:", err);
      } finally {
        setIsLoadingCalls(false);
      }
    };
    
    fetchExotelCalls();
  }, []);

  const triggerCall = (leadIdOrNumber, isExotelInbound = false) => {
    let callerName = '';
    let phoneNum = '';
    let agentName = '';

    if (isExotelInbound) {
      const crmUser = crmUsers.find(u => u.virtualNumber === leadIdOrNumber);
      if (!crmUser) return;
      callerName = `Inbound [${crmUser.businessName}]`;
      phoneNum = leadIdOrNumber;
      agentName = crmUser.assignedAgent;
    } else {
      const lead = leads.find(l => l.id === leadIdOrNumber);
      if (!lead) return;
      callerName = lead.name;
      phoneNum = lead.phone;
      agentName = lead.assignedAgent;

      setLeads(prev => prev.map(l => {
        if (l.id === leadIdOrNumber) return { ...l, status: 'In Progress' };
        return l;
      }));
    }

    const newCallId = Date.now();
    const newCall = {
      id: newCallId,
      caller_name: callerName,
      phone_number: phoneNum,
      status: 'In Progress',
      call_duration: 0,
      created_at: new Date().toISOString(),
      latency: { stt: 'Calculating...', llm: 'Calculating...', tts: 'Calculating...', total: 'Calculating...' },
      transcript: `[Establishing connection via Exotel virtual number: ${phoneNum}]\nConnecting to voice agent persona: ${agentName}...`,
      ai_response: 'Pipelining Call Trunk...'
    };

    setCalls(prev => [newCall, ...prev]);

    setTimeout(() => {
      setCalls(prev => prev.map(c => {
        if (c.id === newCallId) {
          return {
            ...c,
            call_duration: 15,
            transcript: `[Exotel Call Connected]\nCaller: Hello, I saw this number on the advertisement. Who is speaking?\nAI (${agentName}): Hi! Thank you for calling. I am your automated AI business agent. How can I assist you with your requirements today?`
          };
        }
        return c;
      }));
    }, 4000);

    setTimeout(() => {
      const dialoguePool = [
        {
          transcript: `[Exotel Inbound Call Handled]\nCaller: Hello, I saw this number on the advertisement. Who is speaking?\nAI (${agentName}): Hi! Thank you for calling. I am your automated AI business agent. How can I assist you with your requirements today?\nCaller: I wanted to check if you have any properties available in Sector 45.\nAI (${agentName}): Yes! We have two premium residential listings in Sector 45. I can send the catalog link to your mobile number.`,
          ai_response: 'Dispatched Sector 45 catalog SMS link. Logged intent.'
        },
        {
          transcript: `[Exotel Inbound Call Handled]\nCaller: Hi, I needed support with my recent payment invoice.\nAI (${agentName}): No worries! I can check that for you. Can you tell me your billing ID?\nCaller: Billing ID is 9874.\nAI (${agentName}): Got it! Invoice 9874 was processed successfully. It has been sent to your email.`,
          ai_response: 'Invoice email resent. Completed support request.'
        }
      ];

      const chosenDialogue = dialoguePool[Math.floor(Math.random() * dialoguePool.length)];
      const finalStatus = Math.random() > 0.1 ? 'Completed' : 'Failed';
      const duration = Math.floor(Math.random() * 45) + 30;

      setCalls(prev => prev.map(c => {
        if (c.id === newCallId) {
          return {
            ...c,
            status: finalStatus,
            call_duration: duration,
            latency: { stt: '160ms', llm: '590ms', tts: '380ms', total: '1.13s' },
            transcript: chosenDialogue.transcript,
            ai_response: chosenDialogue.ai_response
          };
        }
        return c;
      }));

      if (!isExotelInbound) {
        setLeads(prev => prev.map(l => {
          if (l.id === leadIdOrNumber) {
            return {
              ...l,
              status: finalStatus === 'Completed' ? 'Called' : 'Failed',
              lastCallDate: new Date().toISOString().split('T')[0]
            };
          }
          return l;
        }));
      }

      setMetrics(prev => ({
        ...prev,
        totalCalls: prev.totalCalls + 1
      }));
    }, 9000);
  };

  return { calls, setCalls, triggerCall, isLoadingCalls };
};
