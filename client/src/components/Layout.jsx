import { useLocation } from "react-router-dom";
import Sidebar from "./Sidebar.jsx";
import Topbar from "./Topbar.jsx";
import GridOverlay from "./GridOverlay.jsx";

export default function Layout({
  children,
  overviewMode,
  setOverviewMode,
  isModeSwitching = false,
}) {
  const { pathname } = useLocation();
  const isOverviewRoute = pathname === "/overview";
  const isFrontpage = isOverviewRoute && overviewMode === "frontpage";

  return (
    <div
      className={`app-shell ${isFrontpage ? "overview-frontpage-shell" : ""} ${
        isModeSwitching ? "mode-switching" : ""
      }`}
    >
      <GridOverlay />
      {!isFrontpage && <Sidebar />}
      <main className={`main ${isFrontpage ? "overview-frontpage-main" : ""}`}>
        {!isFrontpage && (
          <Topbar overviewMode={overviewMode} setOverviewMode={setOverviewMode} />
        )}

        <div className={`content ${isFrontpage ? "content-frontpage" : ""}`}>
          {children}
        </div>
      </main>
    </div>
  );
}
