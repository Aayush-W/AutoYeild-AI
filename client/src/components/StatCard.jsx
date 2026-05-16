export default function StatCard({ title, value, foot, chip, chipVariant }) {
  const chipClass = chipVariant ? `chip ${chipVariant}` : "chip";
  return (
    <div className="card">
      <h3>{title}</h3>
      <div className="stat-value">{value}</div>
      {chip ? <div className={chipClass}>{chip}</div> : null}
      {foot ? <div className="stat-foot">{foot}</div> : null}
    </div>
  );
}
