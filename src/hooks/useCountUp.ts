import { useEffect, useRef, useState } from 'react';
import { usePrefersReducedMotion } from './usePrefersReducedMotion';

const easeOutCubic = (t: number) => 1 - Math.pow(1 - t, 3);

export const useCountUp = (target: number, duration = 900): number => {
  const prefersReduced = usePrefersReducedMotion();
  const [display, setDisplay] = useState<number>(prefersReduced ? target : 0);
  const lastShownRef = useRef<number>(prefersReduced ? target : 0);
  const frameRef = useRef<number | null>(null);

  useEffect(() => {
    if (prefersReduced) {
      lastShownRef.current = target;
      setDisplay(target);
      return;
    }

    const from = lastShownRef.current;
    const delta = target - from;

    if (delta === 0) {
      setDisplay(target);
      return;
    }

    const start = performance.now();

    const tick = (now: number) => {
      const progress = Math.min((now - start) / duration, 1);
      const value = from + delta * easeOutCubic(progress);
      lastShownRef.current = value;
      setDisplay(value);
      if (progress < 1) {
        frameRef.current = requestAnimationFrame(tick);
      } else {
        frameRef.current = null;
        lastShownRef.current = target;
        setDisplay(target);
      }
    };

    frameRef.current = requestAnimationFrame(tick);

    return () => {
      if (frameRef.current !== null) {
        cancelAnimationFrame(frameRef.current);
        frameRef.current = null;
      }
    };
  }, [target, duration, prefersReduced]);

  return display;
};