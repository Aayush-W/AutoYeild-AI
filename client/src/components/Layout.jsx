import { useEffect, useState } from "react";
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
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);
  const isOverviewRoute = pathname === "/overview";
  const isFrontpage = isOverviewRoute && overviewMode === "frontpage";

  useEffect(() => {
    setIsSidebarOpen(false);
  }, [pathname]);

  useEffect(() => {
    if (typeof window === "undefined") {
      return undefined;
    }

    const syncSidebarMode = () => {
      if (window.innerWidth > 899) {
        setIsSidebarOpen(false);
      }
    };

    syncSidebarMode();
    window.addEventListener("resize", syncSidebarMode);
    return () => window.removeEventListener("resize", syncSidebarMode);
  }, []);

  return (
    <div
      className={`app-shell ${isFrontpage ? "overview-frontpage-shell" : ""} ${
        isModeSwitching ? "mode-switching" : ""
      } ${isSidebarOpen ? "sidebar-open" : ""} ${
        !isFrontpage ? "workspace-shell" : ""
      }`}
    >
      <GridOverlay />
      {!isFrontpage && (
        <>
          <Sidebar
            isOpen={isSidebarOpen}
            onClose={() => setIsSidebarOpen(false)}
          />
          <button
            type="button"
            className={`sidebar-backdrop ${isSidebarOpen ? "visible" : ""}`}
            onClick={() => setIsSidebarOpen(false)}
            aria-label="Close navigation"
          />
        </>
      )}
      <main className={`main ${isFrontpage ? "overview-frontpage-main" : ""}`}>
        {!isFrontpage && (
          <Topbar
            overviewMode={overviewMode}
            setOverviewMode={setOverviewMode}
            onToggleSidebar={() => setIsSidebarOpen((current) => !current)}
          />
        )}

        <div className={`content ${isFrontpage ? "content-frontpage" : ""}`}>
          {children}
        </div>
      </main>
    </div>
  );
}
