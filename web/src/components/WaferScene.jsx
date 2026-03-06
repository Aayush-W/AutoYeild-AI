import TechnicalAnnotation from "./TechnicalAnnotation.jsx";

const ANNOTATIONS = [
    { label: "PROCESS NODE", value: "12nm FinFET", x: "20%", y: "25%", direction: "right" },
    { label: "ACTIVE LAYER", value: "M2_Cu", x: "72%", y: "22%", direction: "left" },
    { label: "SCAN MODE", value: "SEM High-Res", x: "15%", y: "55%", direction: "right" },
    { label: "MODEL ENGINE", value: "DefectNet-v4.2", x: "75%", y: "55%", direction: "left" },
    { label: "YIELD RATE", value: "99.2%", x: "25%", y: "78%", direction: "right" },
    { label: "SCAN STATUS", value: "ONLINE", x: "68%", y: "78%", direction: "left" },
];

export default function WaferScene() {
    return (
        <div className="wafer-scene">
            {/* Annotation layer */}
            {ANNOTATIONS.map((ann) => (
                <TechnicalAnnotation key={ann.label} {...ann} />
            ))}

            {/* 3D Wafer */}
            <div className="wafer-wrapper">
                <div className="wafer-3d">
                    {/* Wafer body */}
                    <div className="wafer-body">
                        {/* Die grid pattern */}
                        <div className="die-grid">
                            {Array.from({ length: 64 }).map((_, i) => (
                                <div
                                    key={i}
                                    className="die-cell"
                                    style={{
                                        opacity: (() => {
                                            // simulate circular wafer edge mask
                                            const row = Math.floor(i / 8);
                                            const col = i % 8;
                                            const dx = col - 3.5;
                                            const dy = row - 3.5;
                                            const dist = Math.sqrt(dx * dx + dy * dy);
                                            return dist > 3.8 ? 0 : dist > 3.2 ? 0.3 : 1;
                                        })(),
                                    }}
                                />
                            ))}
                        </div>

                        {/* Concentric rings */}
                        {[90, 75, 60, 45, 30, 15].map((size, i) => (
                            <div
                                key={i}
                                className="wafer-ring"
                                style={{
                                    width: `${size}%`,
                                    height: `${size}%`,
                                    opacity: 0.12 + i * 0.04,
                                }}
                            />
                        ))}

                        {/* Center die */}
                        <div className="wafer-center-die" />

                        {/* Defect highlight */}
                        <div className="wafer-defect-marker" />
                    </div>

                    {/* Edge bevel */}
                    <div className="wafer-edge" />
                </div>

                {/* Float shadow */}
                <div className="wafer-shadow" />
            </div>
        </div>
    );
}
