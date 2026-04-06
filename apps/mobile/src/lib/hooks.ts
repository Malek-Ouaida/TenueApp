import { useEffect, useState } from "react";

export function useDebouncedValue<T>(value: T, delayMs: number): T {
  const [debouncedValue, setDebouncedValue] = useState(value);

  useEffect(() => {
    const timeoutId = setTimeout(() => {
      setDebouncedValue(value);
    }, delayMs);

    return () => {
      clearTimeout(timeoutId);
    };
  }, [delayMs, value]);

  return debouncedValue;
}

export function usePolling(
  callback: () => void | Promise<void>,
  enabled: boolean,
  intervalMs: number
) {
  useEffect(() => {
    if (!enabled) {
      return;
    }

    const intervalId = setInterval(() => {
      void callback();
    }, intervalMs);

    return () => {
      clearInterval(intervalId);
    };
  }, [callback, enabled, intervalMs]);
}
