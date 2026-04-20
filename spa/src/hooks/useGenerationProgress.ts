import { useEffect, useRef } from 'react';
import { useAppStore } from '../store/useAppStore';

export const useGenerationProgress = () => {
  const { 
    isGenerating, 
    jobId, 
    progress, 
    logs, 
    startGeneration, 
    updateJobProgress,
    resetJob
  } = useAppStore();
  
  const pollingInterval = useRef<number | null>(null);

  useEffect(() => {
    if (isGenerating && jobId) {
      // Start polling
      pollingInterval.current = window.setInterval(() => {
        updateJobProgress(jobId);
      }, 1000);
    } else {
      // Stop polling
      if (pollingInterval.current) {
        clearInterval(pollingInterval.current);
        pollingInterval.current = null;
      }
    }

    return () => {
      if (pollingInterval.current) {
        clearInterval(pollingInterval.current);
      }
    };
  }, [isGenerating, jobId, updateJobProgress]);

  return {
    progress,
    isGenerating,
    logs,
    start: startGeneration,
    reset: resetJob
  };
};
