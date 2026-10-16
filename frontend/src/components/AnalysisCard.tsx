import type { AnalysisResult } from '../api'

export default function AnalysisCard({ result }: { result: AnalysisResult }) {
  const style = {
    scam: { title: 'Potential Scam', icon: '⚠', tone: 'danger', status: 'Scam indicators detected' },
    not_scam: { title: 'No Scam Indicators Detected', icon: '✓', tone: 'clear', status: 'Not classified as a scam' },
    insufficient_evidence: { title: 'Insufficient Evidence', icon: 'ⓘ', tone: 'uncertain', status: 'Assessment inconclusive' },
  }[result.label]
  const confidence = Number.isFinite(result.confidence) && result.confidence >= 0 && result.confidence <= 1 ? Math.round(result.confidence * 100) : null
  return <section className={`analysis-card ${style.tone}`} aria-label="Scam assessment">
    <header className="analysis-card-heading"><h3><span aria-hidden="true">{style.icon}</span> {style.title}</h3><span>{style.status}</span></header>
    <div className="analysis-card-body">
      {result.address && <p className="analysis-address">{result.address}</p>}
      {confidence !== null && <div className="analysis-meter" role="meter" aria-label="Confidence in assessment" aria-valuemin={0} aria-valuemax={100} aria-valuenow={confidence}><span style={{ width: `${confidence}%` }} /></div>}
      <dl className="analysis-metrics"><div><dt>Confidence level</dt><dd>{confidence === null ? 'Unavailable' : `${confidence}%`}</dd></div><div><dt>Risk classification</dt><dd>{result.risk_type === 'unknown' ? 'Undetermined' : result.risk_type.replaceAll('_', ' ')}</dd></div></dl>
      {result.evidence.length > 0 && <div className="analysis-evidence"><h4>Key risk signals / evidence</h4><ul>{result.evidence.map((item, i) => <li key={i}><span aria-hidden="true">◇</span>{item.description}</li>)}</ul></div>}
      <p className="analysis-source">Analysis source: {result.source}</p>
    </div>
    <footer>Confidence reflects certainty in this assessment, not the probability of a scam. Results are based on available blockchain evidence.</footer>
  </section>
}
