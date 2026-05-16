export default function GridOverlay() {
    return (
        <div
            aria-hidden="true"
            style={{
                position: "fixed",
                inset: 0,
                pointerEvents: "none",
                zIndex: 0,
                backgroundImage: `
          repeating-linear-gradient(
            0deg,
            rgba(0,0,0,0.06) 0px,
            rgba(0,0,0,0.06) 1px,
            transparent 1px,
            transparent 40px
          ),
          repeating-linear-gradient(
            90deg,
            rgba(0,0,0,0.06) 0px,
            rgba(0,0,0,0.06) 1px,
            transparent 1px,
            transparent 40px
          ),
          repeating-linear-gradient(
            0deg,
            rgba(0,0,0,0.08) 0px,
            rgba(0,0,0,0.08) 1px,
            transparent 1px,
            transparent 80px
          ),
          repeating-linear-gradient(
            90deg,
            rgba(0,0,0,0.08) 0px,
            rgba(0,0,0,0.08) 1px,
            transparent 1px,
            transparent 80px
          )
        `,
            }}
        />
    );
}
