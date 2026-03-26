import { Suspense, useEffect, useMemo, useRef, useState } from "react";
import { Canvas, useLoader, useThree } from "@react-three/fiber";
import { Environment, Grid, Html, OrbitControls } from "@react-three/drei";
import * as THREE from "three";

const CELL_SPACING = 0.9;
const CELL_SIZE = 0.78;
const TILE_THICKNESS = 0.05;

const CAMERA_PRESETS = {
  top: [0, 9.8, 0.08],
  isometric: [7.2, 6.0, 7.2],
  side: [10.4, 2.9, 0.08],
};

function createFallbackTileTextureUrl() {
  const canvas = document.createElement("canvas");
  canvas.width = 128;
  canvas.height = 128;
  const ctx = canvas.getContext("2d");
  if (!ctx) return "";
  const gradient = ctx.createLinearGradient(0, 0, 128, 128);
  gradient.addColorStop(0, "#0f172a");
  gradient.addColorStop(1, "#1e293b");
  ctx.fillStyle = gradient;
  ctx.fillRect(0, 0, 128, 128);
  return canvas.toDataURL("image/png");
}

function createTransparentTextureUrl() {
  const canvas = document.createElement("canvas");
  canvas.width = 8;
  canvas.height = 8;
  const ctx = canvas.getContext("2d");
  if (!ctx) return "";
  ctx.clearRect(0, 0, 8, 8);
  return canvas.toDataURL("image/png");
}

function heatmapOpacityForMode(mode, hasHeatmap) {
  if (!hasHeatmap) return 0;
  if (mode === "surface") return 0.06;
  if (mode === "gradient") return 0.12;
  return 0.18;
}

function CameraPresetController({ preset, controlsRef, fitRadius }) {
  const { camera } = useThree();

  useEffect(() => {
    const base = CAMERA_PRESETS[preset] || CAMERA_PRESETS.isometric;
    const scale = Math.max(1, fitRadius / 4.5);
    camera.position.set(base[0] * scale, base[1] * scale, base[2] * scale);
    camera.near = 0.1;
    camera.far = 200;
    camera.updateProjectionMatrix();
    if (controlsRef.current) {
      controlsRef.current.target.set(0, 0, 0);
      controlsRef.current.update();
    } else {
      camera.lookAt(0, 0, 0);
    }
  }, [camera, controlsRef, fitRadius, preset]);

  return null;
}

function GridBoardBase({ mode, boardWidth, boardDepth, combinedAnalysis, fallbackTextureUrl, transparentTextureUrl }) {
  const gridSourceUrl = combinedAnalysis?.grid_image || fallbackTextureUrl;
  const gridHeatmapUrl = combinedAnalysis?.grid_heatmap_image || transparentTextureUrl;
  const [sourceTexture, heatmapTexture] = useLoader(THREE.TextureLoader, [
    gridSourceUrl,
    gridHeatmapUrl,
  ]);

  useMemo(() => {
    [sourceTexture, heatmapTexture].forEach((texture) => {
      texture.colorSpace = THREE.SRGBColorSpace;
      texture.anisotropy = 8;
      texture.needsUpdate = true;
    });
  }, [sourceTexture, heatmapTexture]);

  return (
    <group>
      <mesh receiveShadow castShadow position={[0, 0.008, 0]}>
        <boxGeometry args={[boardWidth + 0.5, 0.09, boardDepth + 0.5]} />
        <meshStandardMaterial color="#1f2937" metalness={0.18} roughness={0.62} />
      </mesh>

      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.056, 0]}>
        <planeGeometry args={[boardWidth, boardDepth]} />
        <meshStandardMaterial map={sourceTexture} color="#ffffff" metalness={0.02} roughness={0.7} />
      </mesh>

      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.0574, 0]}>
        <planeGeometry args={[boardWidth, boardDepth]} />
        <meshStandardMaterial
          map={heatmapTexture}
          transparent
          opacity={mode === "surface" ? 0.08 : mode === "gradient" ? 0.14 : 0.2}
          depthWrite={false}
          blending={THREE.NormalBlending}
          color="#ffffff"
          metalness={0}
          roughness={0.6}
        />
      </mesh>
    </group>
  );
}

function ImageGridTile({
  point,
  mode,
  fallbackTextureUrl,
  transparentTextureUrl,
  isSelected,
  onHover,
  onLeave,
  onSelect,
}) {
  const imageUrl = point.image_data_uri || fallbackTextureUrl;
  const hasHeatmap = Boolean(point.heatmap_image_data_uri);
  const heatmapUrl = point.heatmap_image_data_uri || transparentTextureUrl;
  const [imageTexture, heatmapTexture] = useLoader(THREE.TextureLoader, [imageUrl, heatmapUrl]);

  useMemo(() => {
    [imageTexture, heatmapTexture].forEach((texture) => {
      texture.colorSpace = THREE.SRGBColorSpace;
      texture.anisotropy = 8;
      texture.needsUpdate = true;
    });
  }, [imageTexture, heatmapTexture]);

  const events = {
    onPointerOver: (event) => {
      event.stopPropagation();
      onHover(point);
    },
    onPointerOut: (event) => {
      event.stopPropagation();
      onLeave();
    },
    onClick: (event) => {
      event.stopPropagation();
      onSelect(point);
    },
  };

  return (
    <group position={[point.sceneX, 0, point.sceneZ]}>
      <mesh castShadow receiveShadow {...events} position={[0, 0.09, 0]}>
        <boxGeometry args={[CELL_SIZE, TILE_THICKNESS, CELL_SIZE]} />
        <meshStandardMaterial
          color={isSelected ? "#dbeafe" : "#cbd5e1"}
          metalness={0.06}
          roughness={0.65}
          emissive={isSelected ? "#22d3ee" : "#000000"}
          emissiveIntensity={isSelected ? 0.08 : 0}
        />
      </mesh>

      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.116, 0]} {...events}>
        <planeGeometry args={[CELL_SIZE - 0.02, CELL_SIZE - 0.02]} />
        <meshStandardMaterial map={imageTexture} color="#ffffff" metalness={0.03} roughness={0.7} />
      </mesh>

      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.1172, 0]} {...events}>
        <planeGeometry args={[CELL_SIZE - 0.02, CELL_SIZE - 0.02]} />
        <meshStandardMaterial
          map={heatmapTexture}
          transparent
          opacity={heatmapOpacityForMode(mode, hasHeatmap)}
          depthWrite={false}
          blending={THREE.NormalBlending}
          color="#ffffff"
          metalness={0}
          roughness={0.64}
        />
      </mesh>
    </group>
  );
}

function TileLayer({ points, mode, selectedIndex, onSelect, fallbackTextureUrl, transparentTextureUrl }) {
  const [hovered, setHovered] = useState(null);
  return (
    <>
      {points.map((point) => (
        <ImageGridTile
          key={point.index}
          point={point}
          mode={mode}
          fallbackTextureUrl={fallbackTextureUrl}
          transparentTextureUrl={transparentTextureUrl}
          isSelected={selectedIndex === point.index}
          onHover={setHovered}
          onLeave={() => setHovered(null)}
          onSelect={onSelect}
        />
      ))}
      {hovered && (
        <Html position={[hovered.sceneX, 1.3, hovered.sceneZ]} center distanceFactor={13}>
          <div className="wafer-hover-card">
            <div className="wafer-hover-title">{hovered.label}</div>
            {hovered.image_data_uri && (
              <img src={hovered.image_data_uri} alt={hovered.filename} className="wafer-hover-image" />
            )}
            <div className="wafer-hover-row">Grid: ({hovered.x}, {hovered.y})</div>
            <div className="wafer-hover-row">Region: {hovered.region}</div>
            <div className="wafer-hover-row">Confidence: {(Number(hovered.confidence || 0) * 100).toFixed(1)}%</div>
            <div className="wafer-hover-row">File: {hovered.filename}</div>
          </div>
        </Html>
      )}
    </>
  );
}

function Scene({
  points,
  mode,
  cameraPreset,
  selectedIndex,
  onSelect,
  gridMeta,
  combinedAnalysis,
  fallbackTextureUrl,
  transparentTextureUrl,
}) {
  const boardWidth = gridMeta.cols * CELL_SPACING;
  const boardDepth = gridMeta.rows * CELL_SPACING;
  const floorSize = Math.max(16, Math.max(boardWidth, boardDepth) + 5);
  const fitRadius = Math.max(boardWidth, boardDepth) * 0.55 + 1.8;
  const controlsRef = useRef(null);

  return (
    <>
      <CameraPresetController preset={cameraPreset} controlsRef={controlsRef} fitRadius={fitRadius} />
      <ambientLight intensity={0.44} />
      <directionalLight position={[5, 8, 5]} intensity={1.08} castShadow />
      <directionalLight position={[-5, 4, -5]} intensity={0.34} />

      <Grid
        args={[floorSize, floorSize]}
        cellSize={0.74}
        sectionSize={2.22}
        fadeDistance={26}
        fadeStrength={1}
        cellThickness={0.46}
        sectionThickness={0.86}
        cellColor="#0f2743"
        sectionColor="#0ea5e9"
        position={[0, -0.44, 0]}
      />

      <GridBoardBase
        mode={mode}
        boardWidth={boardWidth}
        boardDepth={boardDepth}
        combinedAnalysis={combinedAnalysis}
        fallbackTextureUrl={fallbackTextureUrl}
        transparentTextureUrl={transparentTextureUrl}
      />
      <TileLayer
        points={points}
        mode={mode}
        selectedIndex={selectedIndex}
        onSelect={onSelect}
        fallbackTextureUrl={fallbackTextureUrl}
        transparentTextureUrl={transparentTextureUrl}
      />

      <Environment preset="city" />
      <OrbitControls
        ref={controlsRef}
        makeDefault
        enablePan
        enableZoom
        enableRotate
        enableDamping
        dampingFactor={0.08}
        minDistance={fitRadius * 0.65}
        maxDistance={fitRadius * 3.4}
        minPolarAngle={0.05}
        maxPolarAngle={Math.PI / 2.01}
      />
    </>
  );
}

export default function WaferDigitalTwin3D({
  points,
  mode = "surface",
  cameraPreset = "isometric",
  selectedCell,
  onSelectCell,
  combinedAnalysis,
}) {
  const fallbackTextureUrl = useMemo(() => createFallbackTileTextureUrl(), []);
  const transparentTextureUrl = useMemo(() => createTransparentTextureUrl(), []);

  const gridMeta = useMemo(() => {
    if (!points || !points.length) return { cols: 1, rows: 1 };
    const maxX = Math.max(...points.map((p) => Number(p.x || 0)));
    const maxY = Math.max(...points.map((p) => Number(p.y || 0)));
    return {
      cols: Math.max(1, maxX + 1),
      rows: Math.max(1, maxY + 1),
    };
  }, [points]);

  const normalizedPoints = useMemo(() => {
    if (!points || !points.length) return [];
    const centerX = (gridMeta.cols - 1) / 2;
    const centerY = (gridMeta.rows - 1) / 2;
    return points.map((point) => ({
      ...point,
      region: String(point.region || "unknown"),
      label: String(point.label || point.defect || "unknown"),
      sceneX: (Number(point.x || 0) - centerX) * CELL_SPACING,
      sceneZ: (Number(point.y || 0) - centerY) * CELL_SPACING,
    }));
  }, [points, gridMeta]);

  return (
    <div className="wafer-3d-frame">
      <Canvas shadows dpr={[1, 1.8]} camera={{ position: CAMERA_PRESETS.isometric, fov: 45 }}>
        <Suspense fallback={null}>
          <Scene
            points={normalizedPoints}
            mode={mode}
            cameraPreset={cameraPreset}
            selectedIndex={selectedCell?.index}
            onSelect={onSelectCell}
            gridMeta={gridMeta}
            combinedAnalysis={combinedAnalysis}
            fallbackTextureUrl={fallbackTextureUrl}
            transparentTextureUrl={transparentTextureUrl}
          />
        </Suspense>
      </Canvas>
    </div>
  );
}
