import { useState, useEffect } from 'react';

export const useMetrics = () => {
  const [metrics, setMetrics] = useState({
    totalCalls: 1420,
    activeCalls: 3,
    avgLatency: '1.24s',
    successRate: '94.2%',
    sttLatency: '180ms',
    llmLatency: '650ms',
    ttsLatency: '410ms',
  });

  // Simulated live updates for active calls ticker
  useEffect(() => {
    const interval = setInterval(() => {
      setMetrics(prev => ({
        ...prev,
        activeCalls: Math.floor(Math.random() * 5) + 1,
        totalCalls: prev.totalCalls + (Math.random() > 0.85 ? 1 : 0),
        avgLatency: (1.1 + Math.random() * 0.25).toFixed(2) + 's'
      }));
    }, 10000);

    return () => clearInterval(interval);
  }, []);

  return { metrics, setMetrics };
};
