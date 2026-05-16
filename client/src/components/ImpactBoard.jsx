function formatInr(value) {
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 0,
  }).format(value);
}

function formatCompactNumber(value, suffix = "") {
  return `${new Intl.NumberFormat("en-IN", {
    maximumFractionDigits: 2,
  }).format(value)}${suffix}`;
}

function ProvenancePill({ tone = "source", children }) {
  return <span className={`impact-provenance ${tone}`}>{children}</span>;
}

function ImpactMetricCard({ title, value, footnote, provenance, tone = "derived" }) {
  return (
    <div className="impact-metric-card">
      <div className="impact-metric-topline">
        <div className="impact-metric-title">{title}</div>
        <ProvenancePill tone={tone}>{provenance}</ProvenancePill>
      </div>
      <div className="impact-metric-value">{value}</div>
      <div className="impact-metric-foot">{footnote}</div>
    </div>
  );
}

export function ImpactBoard({ impactResult }) {
  if (!impactResult) {
    return null;
  }

  return (
    <div className="card">
      <div className="card-header">
        <div className="card-title">
          <span className="material-symbols-rounded">eco</span>
          BATCH IMPACT ESTIMATION
        </div>
        <div className="impact-card-chip">{impactResult.batchId}</div>
      </div>

      <div className="impact-metric-grid">
        <ImpactMetricCard
          title="Carbon Prevented"
          value={`${formatCompactNumber(impactResult.carbonPreventedKgco2e)} kgCO2e`}
          footnote={`${formatCompactNumber(impactResult.energySavedKwh)} kWh x ${impactResult.appliedGridFactorKgco2PerKwh.toFixed(3)} kgCO2e/kWh`}
          provenance="Derived"
          tone="derived"
        />
        <ImpactMetricCard
          title="Energy Saved"
          value={`${formatCompactNumber(impactResult.energySavedKwh)} kWh`}
          footnote={`${formatCompactNumber(impactResult.avoidedScrapWafers)} recovered wafers x ${formatCompactNumber(impactResult.appliedEnergyKwhPerWafer)} kWh/wafer`}
          provenance="Source + Derived"
          tone="source"
        />
        <ImpactMetricCard
          title="Yield Uplift"
          value={`${impactResult.yieldUpliftPp.toFixed(2)} pp`}
          footnote={`Before ${(impactResult.yieldBefore * 100).toFixed(2)}% | After ${(impactResult.yieldAfter * 100).toFixed(2)}%`}
          provenance="Derived"
          tone="derived"
        />
        <ImpactMetricCard
          title="Cost Saved"
          value={formatInr(impactResult.totalCostSavedInr)}
          footnote={`${formatInr(impactResult.scrapCostSavedInr)} scrap + ${formatInr(impactResult.energyCostSavedInr)} energy`}
          provenance="Input + Derived"
          tone="input"
        />
      </div>
    </div>
  );
}

export function ImpactSessionLedger({ impactHistory, impactSummary }) {
  if (!impactHistory.length) {
    return null;
  }

  return (
    <div className="card">
      <div className="card-header">
        <div className="card-title">
          <span className="material-symbols-rounded">timeline</span>
          SESSION IMPACT LEDGER
        </div>
        <div className="impact-card-chip">{impactSummary.batchesAnalyzed} batches</div>
      </div>

      <div className="impact-ledger-summary">
        <div className="impact-ledger-stat">
          <div className="impact-ledger-label">Energy Saved</div>
          <div className="impact-ledger-value">
            {formatCompactNumber(impactSummary.energySavedKwh)} kWh
          </div>
        </div>
        <div className="impact-ledger-stat">
          <div className="impact-ledger-label">CO2e Prevented</div>
          <div className="impact-ledger-value">
            {formatCompactNumber(impactSummary.carbonPreventedKgco2e)} kg
          </div>
        </div>
        <div className="impact-ledger-stat">
          <div className="impact-ledger-label">Avg Yield Uplift</div>
          <div className="impact-ledger-value">
            {impactSummary.avgYieldUpliftPp.toFixed(2)} pp
          </div>
        </div>
        <div className="impact-ledger-stat">
          <div className="impact-ledger-label">Cost Saved</div>
          <div className="impact-ledger-value">
            {formatInr(impactSummary.totalCostSavedInr)}
          </div>
        </div>
      </div>

      <div className="impact-ledger-table">
        <div className="impact-ledger-head">
          {["Batch", "Class", "Energy", "CO2e", "Yield", "Cost"].map((header) => (
            <div key={header}>{header}</div>
          ))}
        </div>
        {[...impactHistory].reverse().map((item) => (
          <div className="impact-ledger-row" key={`${item.inspectionId}-${item.timestamp}`}>
            <div>{item.batchId}</div>
            <div style={{ textTransform: "uppercase" }}>{item.defectClass}</div>
            <div>{formatCompactNumber(item.energySavedKwh)} kWh</div>
            <div>{formatCompactNumber(item.carbonPreventedKgco2e)} kg</div>
            <div>{item.yieldUpliftPp.toFixed(2)} pp</div>
            <div>{formatInr(item.totalCostSavedInr)}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

export function ImpactSourceCard({ impactResult }) {
  if (!impactResult) {
    return null;
  }

  const { energyProfile, gridProfile } = impactResult.sources;

  return (
    <div className="card">
      <div className="card-header">
        <div className="card-title">
          <span className="material-symbols-rounded">library_books</span>
          SOURCES & METHODOLOGY
        </div>
      </div>

      <div className="impact-source-list">
        <div className="impact-source-item">
          <div className="impact-source-name">Semiconductor energy intensity</div>
          <div className="impact-source-value">
            {energyProfile.energyKwhPerCm2.toFixed(3)} kWh/cm2
          </div>
          <div className="impact-source-meta">
            {energyProfile.sourceTitle} ({energyProfile.publicationYear})
          </div>
          <a href={energyProfile.sourceUrl} target="_blank" rel="noreferrer">
            Primary source
          </a>
        </div>
        <div className="impact-source-item">
          <div className="impact-source-name">India grid carbon factor</div>
          <div className="impact-source-value">
            {gridProfile.factorValueKgco2PerKwh.toFixed(3)} kgCO2e/kWh
          </div>
          <div className="impact-source-meta">
            {gridProfile.sourceTitle} ({gridProfile.publicationYear})
          </div>
          <a href={gridProfile.sourceUrl} target="_blank" rel="noreferrer">
            Official source
          </a>
        </div>
      </div>

      <div className="impact-formula-block">
        <div className="impact-formula-title">Applied formulas</div>
        <div className="impact-formula-line">
          Energy saved = avoided scrap wafers x applied energy per wafer
        </div>
        <div className="impact-formula-line">
          Carbon prevented = energy saved x applied grid factor
        </div>
        <div className="impact-formula-line">
          Yield uplift = (yield_after - yield_before) x 100
        </div>
        <div className="impact-formula-line">
          Cost saved = scrap cost saved + energy cost saved
        </div>
      </div>
    </div>
  );
}
