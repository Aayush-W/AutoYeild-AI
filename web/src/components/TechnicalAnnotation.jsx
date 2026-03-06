/* Technical Annotation Component — Engineering callout style */
export default function TechnicalAnnotation({
    label,
    value,
    x,
    y,
    direction = "right",
    className = "",
    lineLength = 60,
    boxWidth = 140,
    boxHeight = 48,
    showBox = true,
}) {
    const boxW = boxWidth;
    const boxH = boxHeight;

    let lineX2, lineY2, boxX, boxY;

    switch (direction) {
        case "right":
            lineX2 = lineLength;
            lineY2 = 0;
            boxX = lineLength + 1;
            boxY = -(boxH / 2);
            break;
        case "left":
            lineX2 = -lineLength;
            lineY2 = 0;
            boxX = -(lineLength + boxW + 1);
            boxY = -(boxH / 2);
            break;
        case "top":
            lineX2 = 0;
            lineY2 = -lineLength;
            boxX = -(boxW / 2);
            boxY = -(lineLength + boxH + 1);
            break;
        case "bottom":
            lineX2 = 0;
            lineY2 = lineLength;
            boxX = -(boxW / 2);
            boxY = lineLength + 1;
            break;
        case "bottom-right":
            lineX2 = lineLength;
            lineY2 = lineLength;
            boxX = lineLength + 1;
            boxY = lineLength - boxH / 2;
            break;
        case "top-right":
            lineX2 = lineLength;
            lineY2 = -lineLength;
            boxX = lineLength + 1;
            boxY = -lineLength - boxH / 2;
            break;
        case "bottom-left":
            lineX2 = -lineLength;
            lineY2 = lineLength;
            boxX = -(lineLength + boxW + 1);
            boxY = lineLength - boxH / 2;
            break;
        case "top-left":
            lineX2 = -lineLength;
            lineY2 = -lineLength;
            boxX = -(lineLength + boxW + 1);
            boxY = -lineLength - boxH / 2;
            break;
        default:
            lineX2 = lineLength;
            lineY2 = 0;
            boxX = lineLength + 1;
            boxY = -(boxH / 2);
    }

    return (
        <div
            className={`annotation ${className}`}
            style={{ position: "absolute", left: x, top: y, pointerEvents: "none" }}
        >
            {/* Anchor node */}
            <div
                style={{
                    position: "absolute",
                    width: 10,
                    height: 10,
                    background: "#111",
                    transform: "translate(-5px,-5px)",
                    zIndex: 2,
                }}
            >
                <div
                    style={{
                        position: "absolute",
                        width: 4,
                        height: 4,
                        background: "#F4F4F2",
                        top: "50%",
                        left: "50%",
                        transform: "translate(-50%,-50%)",
                    }}
                />
            </div>

            {/* SVG connector line */}
            <svg
                style={{
                    position: "absolute",
                    overflow: "visible",
                    top: 0,
                    left: 0,
                }}
                width={Math.abs(lineX2) + 1}
                height={Math.abs(lineY2) + 1}
            >
                <line
                    x1={0}
                    y1={0}
                    x2={lineX2}
                    y2={lineY2}
                    stroke="#2B2B2B"
                    strokeWidth={1}
                />
            </svg>

            {/* Callout box */}
            {showBox && (
                <div
                    style={{
                        position: "absolute",
                        left: boxX,
                        top: boxY,
                        width: boxW,
                        height: boxH,
                        border: "1px solid #111111",
                        background: "#F4F4F2",
                        borderRadius: 0,
                        padding: "8px 12px",
                        display: "flex",
                        flexDirection: "column",
                        justifyContent: "center",
                        gap: 2,
                    }}
                >
                    <div
                        style={{
                            fontFamily: "'JetBrains Mono', monospace",
                            fontSize: 9,
                            fontWeight: 600,
                            color: "#6E6E6E",
                            textTransform: "uppercase",
                            letterSpacing: "0.08em",
                        }}
                    >
                        {label}
                    </div>
                    <div
                        style={{
                            fontFamily: "'JetBrains Mono', monospace",
                            fontSize: 11,
                            fontWeight: 700,
                            color: "#111111",
                            letterSpacing: "0.02em",
                        }}
                    >
                        {value}
                    </div>
                </div>
            )}
        </div>
    );
}
