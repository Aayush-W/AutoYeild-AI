import Sidebar from "./Sidebar.jsx";
import Topbar from "./Topbar.jsx";
import GridOverlay from "./GridOverlay.jsx";

export default function Layout({ children }) {
  return (
    <div className="app-shell">
      <GridOverlay />
      <Sidebar />
      <main className="main">
        <Topbar />
        <div className="content">{children}</div>
      </main>
    </div>
  );
}
