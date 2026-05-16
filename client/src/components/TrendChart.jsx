export default function TrendChart({ bars }) {
  return (
    <div className="card">
      <h3>Confidence Trend</h3>
      <div className="trend-bars">
        {bars.map((value, index) => (
          <div
            key={`bar-${index}`}
            className="trend-bar"
            style={{ height: `${value}%` }}
          />
        ))}
      </div>
      <div className="stat-foot" style={{ marginTop: 8 }}>
        -24h &nbsp;&nbsp;&nbsp;&nbsp; -12h &nbsp;&nbsp;&nbsp;&nbsp; Now
      </div>
    </div>
  );
}
