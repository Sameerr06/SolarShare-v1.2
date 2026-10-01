import { useEffect } from 'react';
import { useLocation } from 'react-router-dom';
import { usePrefersReducedMotion } from './usePrefersReducedMotion';

export const useScrollToTopOnNavigate = (): void => {
  const { pathname } = useLocation();
  const prefersReduced = usePrefersReducedMotion();

  useEffect(() => {
    window.scrollTo({ top: 0, left: 0, behavior: prefersReduced ? 'auto' : 'smooth' });
  }, [pathname, prefersReduced]);
};