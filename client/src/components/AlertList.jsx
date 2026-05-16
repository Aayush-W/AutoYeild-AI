export default function AlertList({ alerts }) {
  return (
    <div className="card">
      <h3>Active Alerts</h3>
      <div className="inspection-list">
        {alerts.map((alert) => (
          <div key={alert.id} className={`alert ${alert.variant}`}>
            <div>
              <div style={{ fontWeight: 600 }}>{alert.title}</div>
              <div className="stat-foot">{alert.detail}</div>
            </div>
            <div className="stat-foot">{alert.time}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
