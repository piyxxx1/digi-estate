import { useState, useEffect } from 'react';

export const useMetrics = () => {
  const [metrics, setMetrics] = useState({
    totalCalls: 0,
    inboundCalls: 0,
    outboundCalls: 0,
    completedCalls: 0,
    activeCalls: 0,
    avgLatency: '1.08s',
    successRate: '100%',
    totalDurationMinutes: 0,
    avgDuration: '0s',
    totalSpendINR: 0,
    activeCompanies: 0,
    sttEngine: 'Sarvam AI Realtime (16kHz)',
    llmEngine: 'gemini-2.5-flash',
    ttsEngine: 'Sarvam Bulbul',
    sttLatency: '180ms',
    llmLatency: '550ms',
    ttsLatency: '350ms',
  });

  const [companyUsage, setCompanyUsage] = useState([]);
  const [telemetryRaw, setTelemetryRaw] = useState(null);
  const [isLoadingTelemetry, setIsLoadingTelemetry] = useState(true);

  const fetchTelemetry = async () => {
    try {
      const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';
      const res = await fetch(`${API_BASE_URL}/api/telemetry/system-overview`);
      if (res.ok) {
        const data = await res.json();
        setTelemetryRaw(data);
        if (data.summary) {
          setMetrics(prev => ({
            ...prev,
            totalCalls: data.summary.total_calls,
            inboundCalls: data.summary.inbound_calls,
            outboundCalls: data.summary.outbound_calls,
            completedCalls: data.summary.completed_calls,
            activeCalls: 1, // Active telephony listener channel
            successRate: data.summary.success_rate,
            totalDurationMinutes: data.summary.total_duration_minutes,
            avgDuration: data.summary.avg_call_duration,
            totalSpendINR: data.summary.total_spend_inr,
            activeCompanies: data.summary.active_companies,
            sttEngine: data.summary.stt_engine,
            llmEngine: data.summary.llm_engine,
            ttsEngine: data.summary.tts_engine,
            avgLatency: data.summary.avg_latency,
          }));
        }
        if (data.companies) {
          setCompanyUsage(data.companies);
        }
      }
    } catch (err) {
      console.error("Failed to load telemetry overview:", err);
    } finally {
      setIsLoadingTelemetry(false);
    }
  };

  useEffect(() => {
    fetchTelemetry();
    // Poll telemetry every 15 seconds for live real-time updates
    const interval = setInterval(fetchTelemetry, 15000);
    return () => clearInterval(interval);
  }, []);

  return { metrics, setMetrics, companyUsage, telemetryRaw, isLoadingTelemetry, refreshTelemetry: fetchTelemetry };
};
