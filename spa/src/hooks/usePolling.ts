import { useEffect, useEffectEvent } from "react";

export function usePolling(
  enabled: boolean,
  refresh: (signal: AbortSignal) => Promise<void>,
) {
  const refreshLatest = useEffectEvent(refresh);

  useEffect(() => {
    if (!enabled) return;
    const controller = new AbortController();
    let timer: number;
    const poll = async () => {
      try {
        await refreshLatest(controller.signal);
      } catch (error) {
        if (!controller.signal.aborted) console.error(error);
      } finally {
        if (!controller.signal.aborted) {
          timer = window.setTimeout(poll, 3000);
        }
      }
    };
    timer = window.setTimeout(poll, 3000);
    return () => {
      window.clearTimeout(timer);
      controller.abort();
    };
  }, [enabled]);
}

export function isActiveTask(status: string) {
  return status === "queued" || status === "running";
}
