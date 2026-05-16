export default function InspectionList({ items }) {
  return (
    <div className="card">
      <h3>Recent Inspections</h3>
      <div className="inspection-list">
        {items.map((item) => (
          <div className="inspection-item" key={item.id}>
            <div className="inspection-left">
              <div className="badge">+</div>
              <div>
                <div style={{ fontWeight: 600 }}>{item.label}</div>
                <div className="stat-foot">{item.time}</div>
              </div>
            </div>
            <div className="progress">
              <span style={{ width: `${item.score}%` }} />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
