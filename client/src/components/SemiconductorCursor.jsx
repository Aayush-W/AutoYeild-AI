import { useEffect, useRef, useState } from "react";

const TRAIL_SEGMENTS = 8;
const INTERACTIVE_SELECTOR = [
  "a",
  "button",
  "[role='button']",
  "input",
  "select",
  "textarea",
  ".ov-thread-item",
  ".metric-card",
  ".card",
  ".chip",
  ".ov-def-box",
  ".ov-desc-box",
  ".topbar-mode-toggle",
  ".overview-floating-toggle",
].join(",");

export default function SemiconductorCursor() {
  const cursorRef = useRef(null);
  const trailRefs = useRef([]);
  const rafRef = useRef(null);
  const mouseRef = useRef({ x: 0, y: 0 });
  const activeRef = useRef(false);
  const hoverRef = useRef(false);
  const [isFinePointer, setIsFinePointer] = useState(false);
  const [reducedMotion, setReducedMotion] = useState(false);

  useEffect(() => {
    if (typeof window === "undefined") {
      return undefined;
    }

    const pointerQuery = window.matchMedia("(pointer: fine)");
    const reduceQuery = window.matchMedia("(prefers-reduced-motion: reduce)");
    const sync = () => {
      setIsFinePointer(pointerQuery.matches);
      setReducedMotion(reduceQuery.matches);
    };

    sync();
    pointerQuery.addEventListener("change", sync);
    reduceQuery.addEventListener("change", sync);

    return () => {
      pointerQuery.removeEventListener("change", sync);
      reduceQuery.removeEventListener("change", sync);
    };
  }, []);

  useEffect(() => {
    if (!isFinePointer) {
      return undefined;
    }

    const root = document.documentElement;
    root.classList.add("overview-custom-cursor");

    const onMove = (event) => {
      mouseRef.current = { x: event.clientX, y: event.clientY };
      activeRef.current = true;

      const isHoveringInteractive = Boolean(
        event.target?.closest?.(INTERACTIVE_SELECTOR)
      );

      if (hoverRef.current !== isHoveringInteractive && cursorRef.current) {
        hoverRef.current = isHoveringInteractive;
        cursorRef.current.classList.toggle("is-hover", isHoveringInteractive);
      }
    };

    const onLeave = () => {
      activeRef.current = false;
      cursorRef.current?.classList.add("is-hidden");
    };

    const onEnter = () => {
      cursorRef.current?.classList.remove("is-hidden");
    };

    window.addEventListener("mousemove", onMove, { passive: true });
    document.addEventListener("mouseleave", onLeave);
    document.addEventListener("mouseenter", onEnter);

    if (reducedMotion) {
      const staticFollow = () => {
        if (cursorRef.current) {
          const { x, y } = mouseRef.current;
          cursorRef.current.style.transform = `translate3d(${x}px, ${y}px, 0)`;
        }
        rafRef.current = requestAnimationFrame(staticFollow);
      };
      rafRef.current = requestAnimationFrame(staticFollow);
    } else {
      const positions = Array.from({ length: TRAIL_SEGMENTS + 1 }, () => ({
        x: window.innerWidth / 2,
        y: window.innerHeight / 2,
      }));

      const animate = () => {
        const { x: mx, y: my } = mouseRef.current;
        positions[0].x += (mx - positions[0].x) * 0.36;
        positions[0].y += (my - positions[0].y) * 0.36;

        for (let i = 1; i < positions.length; i += 1) {
          positions[i].x += (positions[i - 1].x - positions[i].x) * 0.34;
          positions[i].y += (positions[i - 1].y - positions[i].y) * 0.34;
        }

        if (cursorRef.current) {
          cursorRef.current.style.transform = `translate3d(${positions[0].x}px, ${positions[0].y}px, 0)`;
          cursorRef.current.classList.toggle("is-hidden", !activeRef.current);
        }

        trailRefs.current.forEach((trailNode, index) => {
          if (!trailNode) {
            return;
          }
          const p = positions[index + 1];
          const fade = 1 - index / TRAIL_SEGMENTS;
          trailNode.style.opacity = activeRef.current ? `${fade * 0.7}` : "0";
          trailNode.style.transform = `translate3d(${p.x}px, ${p.y}px, 0) scale(${0.4 + fade * 0.85})`;
        });

        rafRef.current = requestAnimationFrame(animate);
      };

      rafRef.current = requestAnimationFrame(animate);
    }

    return () => {
      root.classList.remove("overview-custom-cursor");
      window.removeEventListener("mousemove", onMove);
      document.removeEventListener("mouseleave", onLeave);
      document.removeEventListener("mouseenter", onEnter);
      if (rafRef.current) {
        cancelAnimationFrame(rafRef.current);
      }
    };
  }, [isFinePointer, reducedMotion]);

  if (!isFinePointer) {
    return null;
  }

  return (
    <div className="semicursor-layer" aria-hidden="true">
      {!reducedMotion &&
        Array.from({ length: TRAIL_SEGMENTS }).map((_, index) => (
          <span
            key={index}
            className="semicursor-trail"
            ref={(node) => {
              trailRefs.current[index] = node;
            }}
          />
        ))}

      <div ref={cursorRef} className="semicursor-core is-hidden">
        <span className="semicursor-ring" />
        <span className="semicursor-h" />
        <span className="semicursor-v" />
        <span className="semicursor-dot" />
      </div>
    </div>
  );
}
