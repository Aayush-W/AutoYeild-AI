import { useEffect, useMemo, useRef, useState } from "react";
import TechnicalAnnotation from "./TechnicalAnnotation.jsx";

const DESKTOP_ANNOTATIONS = [
  {
    label: "PROCESS NODE",
    value: "12nm FinFET",
    x: "43%",
    y: "26%",
    direction: "left",
    lineLength: 44,
    boxWidth: 144,
  },
  {
    label: "ACTIVE LAYER",
    value: "M2_Cu",
    x: "57%",
    y: "26%",
    direction: "right",
    lineLength: 44,
    boxWidth: 144,
  },
  {
    label: "SCAN MODE",
    value: "SEM High-Res",
    x: "43%",
    y: "64%",
    direction: "left",
    lineLength: 44,
    boxWidth: 142,
  },
  {
    label: "MODEL ENGINE",
    value: "DefectNet-v4.2",
    x: "57%",
    y: "64%",
    direction: "right",
    lineLength: 44,
    boxWidth: 148,
  },
  {
    label: "SCAN STATUS",
    value: "ONLINE",
    x: "50%",
    y: "84%",
    direction: "bottom",
    lineLength: 52,
    boxWidth: 160,
    boxHeight: 44,
  },
];

const TABLET_ANNOTATIONS = [
  {
    label: "PROCESS NODE",
    value: "12nm FinFET",
    x: "44%",
    y: "27%",
    direction: "left",
    lineLength: 34,
    boxWidth: 122,
    boxHeight: 44,
  },
  {
    label: "MODEL ENGINE",
    value: "DefectNet-v4.2",
    x: "56%",
    y: "27%",
    direction: "right",
    lineLength: 34,
    boxWidth: 126,
    boxHeight: 44,
  },
  {
    label: "SCAN STATUS",
    value: "ONLINE",
    x: "50%",
    y: "82%",
    direction: "bottom",
    lineLength: 44,
    boxWidth: 128,
    boxHeight: 42,
  },
];

const WORKSPACE_ANNOTATIONS = [
  {
    label: "PROCESS NODE",
    value: "12nm FinFET",
    x: "45%",
    y: "29%",
    direction: "left",
    lineLength: 30,
    boxWidth: 118,
    boxHeight: 40,
  },
  {
    label: "ACTIVE LAYER",
    value: "M2_Cu",
    x: "55%",
    y: "29%",
    direction: "right",
    lineLength: 30,
    boxWidth: 118,
    boxHeight: 40,
  },
  {
    label: "SCAN MODE",
    value: "SEM High-Res",
    x: "45%",
    y: "64%",
    direction: "left",
    lineLength: 28,
    boxWidth: 116,
    boxHeight: 40,
  },
  {
    label: "MODEL ENGINE",
    value: "DefectNet-v4.2",
    x: "55%",
    y: "64%",
    direction: "right",
    lineLength: 28,
    boxWidth: 124,
    boxHeight: 40,
  },
  {
    label: "SCAN STATUS",
    value: "ONLINE",
    x: "50%",
    y: "79%",
    direction: "bottom",
    lineLength: 28,
    boxWidth: 118,
    boxHeight: 40,
  },
];

const MOBILE_CHIPS = [
  "12nm FinFET",
  "DefectNet-v4.2",
  "SEM High-Res",
  "Yield 99.2%",
  "Scan Online",
];

const PRESET_BY_WIDTH = (width) => {
  if (width >= 1200) return "desktop";
  if (width >= 900) return "tablet";
  return "mobile";
};

const MOTION_SCALE = {
  subtle: 0.62,
  medium: 0.82,
  high: 1,
};

export default function WaferScene({
  annotationPreset = "auto",
  motionLevel = "subtle",
}) {
  const containerRef = useRef(null);
  const [width, setWidth] = useState(
    typeof window === "undefined" ? 1440 : window.innerWidth
  );
  const [prefersReducedMotion, setPrefersReducedMotion] = useState(false);

  useEffect(() => {
    if (typeof window === "undefined") {
      return undefined;
    }

    const onResize = () => setWidth(window.innerWidth);
    const reduceMotionQuery = window.matchMedia("(prefers-reduced-motion: reduce)");
    const syncReducedMotion = () => setPrefersReducedMotion(reduceMotionQuery.matches);

    onResize();
    syncReducedMotion();
    window.addEventListener("resize", onResize);
    reduceMotionQuery.addEventListener("change", syncReducedMotion);

    return () => {
      window.removeEventListener("resize", onResize);
      reduceMotionQuery.removeEventListener("change", syncReducedMotion);
    };
  }, []);

  const resolvedPreset = useMemo(() => {
    if (annotationPreset !== "auto") {
      return annotationPreset;
    }
    return PRESET_BY_WIDTH(width);
  }, [annotationPreset, width]);

  const annotations = useMemo(() => {
    if (resolvedPreset === "workspace") {
      return WORKSPACE_ANNOTATIONS;
    }
    if (resolvedPreset === "desktop") {
      return DESKTOP_ANNOTATIONS;
    }
    if (resolvedPreset === "tablet") {
      return TABLET_ANNOTATIONS;
    }
    return [];
  }, [resolvedPreset]);

  const waferSize = useMemo(() => {
    if (resolvedPreset === "workspace") {
      return "clamp(250px, 27vw, 400px)";
    }
    if (resolvedPreset === "desktop") {
      return "clamp(280px, 30vw, 440px)";
    }
    if (resolvedPreset === "tablet") {
      return "clamp(260px, 42vw, 360px)";
    }
    return "clamp(220px, 70vw, 300px)";
  }, [resolvedPreset]);

  const tiltScale = MOTION_SCALE[motionLevel] ?? MOTION_SCALE.subtle;

  const handleMouseMove = (event) => {
    if (prefersReducedMotion || resolvedPreset === "mobile") {
      return;
    }

    const element = containerRef.current;
    if (!element) {
      return;
    }

    const rect = element.getBoundingClientRect();
    const centerX = rect.left + rect.width / 2;
    const centerY = rect.top + rect.height / 2;
    const deltaX = (event.clientX - centerX) / (rect.width / 2);
    const deltaY = (event.clientY - centerY) / (rect.height / 2);
    const maxY = 6 * tiltScale;
    const maxX = 4.8 * tiltScale;

    element.style.transform = `perspective(900px) rotateY(${deltaX * maxY}deg) rotateX(${
      -deltaY * maxX
    }deg)`;
  };

  const handleMouseLeave = () => {
    const element = containerRef.current;
    if (!element) {
      return;
    }
    element.style.transform = "perspective(900px) rotateY(0deg) rotateX(0deg)";
  };

  return (
    <div className={`wafer-scene wafer-scene--${resolvedPreset}`}>
      {annotations.map((annotation, index) => (
        <TechnicalAnnotation
          key={annotation.label}
          className={`wafer-annotation wafer-annotation-${index + 1}`}
          {...annotation}
        />
      ))}

      <div className="wafer-wrapper" onMouseMove={handleMouseMove} onMouseLeave={handleMouseLeave}>
        <div
          ref={containerRef}
          className="wafer-video-shell"
          style={{
            width: waferSize,
            height: waferSize,
          }}
        >
          <video src="/assets/wafer.mp4" autoPlay loop muted playsInline className="wafer-video" />
          <div className="wafer-scan-overlay" />
          <div className="wafer-vignette-overlay" />
          <div className="wafer-shimmer-overlay" />
        </div>

        <div
          className="wafer-glow-halo"
          style={{
            width: `calc(${waferSize} + 34px)`,
            height: `calc(${waferSize} + 34px)`,
          }}
        />
        <div className="wafer-shadow" />
      </div>

      {resolvedPreset === "mobile" && (
        <div className="wafer-mobile-chips">
          {MOBILE_CHIPS.map((chip) => (
            <span key={chip} className="wafer-mobile-chip">
              {chip}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}
