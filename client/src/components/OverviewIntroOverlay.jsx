import { useCallback, useEffect, useRef, useState } from "react";

const INTRO_DURATION_MS = 2200;
const EXIT_DURATION_MS = 340;

export default function OverviewIntroOverlay({ onComplete }) {
  const [progress, setProgress] = useState(0);
  const [isExiting, setIsExiting] = useState(false);
  const exitTimerRef = useRef(null);
  const didExitRef = useRef(false);

  const startExit = useCallback(() => {
    if (didExitRef.current) {
      return;
    }
    didExitRef.current = true;
    setProgress(100);
    setIsExiting(true);
    exitTimerRef.current = setTimeout(() => {
      onComplete?.();
    }, EXIT_DURATION_MS);
  }, [onComplete]);

  useEffect(() => {
    const startTime = performance.now();
    let rafId = null;

    const animate = (now) => {
      const elapsed = now - startTime;
      const normalized = Math.min(elapsed / (INTRO_DURATION_MS - 300), 1);
      setProgress(Math.round(normalized * 100));

      if (elapsed >= INTRO_DURATION_MS) {
        startExit();
        return;
      }
      rafId = requestAnimationFrame(animate);
    };

    rafId = requestAnimationFrame(animate);

    const onKeyDown = (event) => {
      if (event.key === "Escape" || event.key === "Enter") {
        startExit();
      }
    };

    window.addEventListener("keydown", onKeyDown);

    return () => {
      if (rafId) {
        cancelAnimationFrame(rafId);
      }
      if (exitTimerRef.current) {
        clearTimeout(exitTimerRef.current);
      }
      window.removeEventListener("keydown", onKeyDown);
    };
  }, [startExit]);

  return (
    <div
      className={`overview-intro-overlay ${isExiting ? "is-exiting" : ""}`}
      onClick={startExit}
      role="presentation"
      aria-hidden="true"
    >
      <div className="overview-intro-grid" />

      <div className="overview-intro-center">
        <div className="overview-intro-wordmark">
          <span className="overview-intro-wordmark-auto">AUTO</span>
          <span className="overview-intro-wordmark-yield">YIELD</span>
        </div>
        <div className="overview-intro-subtitle">SEMICONDUCTOR INSPECTION</div>
      </div>

      <div className="overview-intro-loading">LOADING {progress}%</div>
    </div>
  );
}
