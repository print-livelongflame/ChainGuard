import { useState } from 'react'
import type { AnalysisResult, LookupView } from '../api'

const short = (value: string) => value.length > 18 ? `${value.slice(0, 8)}…${value.slice(-6)}` : value
function dateLabel(timestamp: string | number | null | undefined) {
  if (!timestamp) return 'Unavailable'
  const date = /^\d+$/.test(String(timestamp)) ? new Date(Number(timestamp) * 1000) : new Date(timestamp)
  return Number.isNaN(date.getTime()) ? 'Unavailable' : date.toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric', timeZone: 'UTC' })
}

export default function LookupResult({ lookup, assessment }: { lookup: LookupView; assessment?: AnalysisResult | null }) {
  const [limit, setLimit] = useState(10)
  const status = assessment?.label === 'scam' ? 'Scam indicators detected' : assessment?.label === 'not_scam' ? 'Not classified as a scam' : 'Insufficient evidence'
  return <section className="lookup-result" aria-label={lookup.kind === 'transactions' ? 'Transaction analysis' : 'Assessment evidence'}>
    {assessment && <div className={`lookup-summary ${assessment.label}`}><span>Scam Assessment Summary {assessment.address && <span title={assessment.address}>({short(assessment.address)})</span>}</span><strong>{status}</strong></div>}
    {lookup.kind === 'transactions' ? <>
      <h3>Transaction Analysis</h3>
      <p className="lookup-caption">{lookup.address && <span title={lookup.address}>{short(lookup.address)} · </span>}{lookup.chain === 'ethereum' ? 'Ethereum' : lookup.chain} · Amounts in native currency · Dates in UTC</p>
      {lookup.provenance.status === 'pass' && lookup.transactions.length > 0 ? <>
        <div className="transaction-table-scroll"><table className="transaction-table"><thead><tr><th>Hash</th><th>Type</th><th>Amount</th><th>Date</th><th>Risk status</th></tr></thead><tbody>{lookup.transactions.slice(0, limit).map((transaction, index) => <tr key={`${transaction.hash}-${index}`}>
          <td>{transaction.hash && /^0x[a-fA-F0-9]{64}$/.test(transaction.hash) && lookup.chain === 'ethereum' ? <a href={`https://etherscan.io/tx/${transaction.hash}`} target="_blank" rel="noreferrer" title={transaction.hash}>{short(transaction.hash)}</a> : <span title={transaction.hash ?? ''}>{transaction.hash ? short(transaction.hash) : 'Unavailable'}</span>}</td>
          <td title={transaction.method ?? ''}>{transaction.method || 'Unknown'}</td>
          <td>{transaction.value == null || transaction.value === '' ? 'Unavailable' : `${transaction.value}${lookup.chain === 'ethereum' ? ' ETH' : ''}`}</td>
          <td>{dateLabel(transaction.timestamp)}</td><td><span className="transaction-status">Not assessed</span></td>
        </tr>)}</tbody></table></div>
        <p className="transaction-count">Showing {Math.min(limit, lookup.transactions.length)} of {lookup.transactions.length} fetched transactions{limit < lookup.transactions.length && <button type="button" onClick={() => setLimit(value => value + 10)}>Show more</button>}</p>
      </> : <div className="lookup-empty">{lookup.provenance.status === 'pass' ? 'No transactions were returned by this lookup.' : lookup.provenance.status === 'fail' ? 'Transaction history could not be retrieved. Please run a new lookup to try again.' : 'Transaction history was not fetched for this analysis. Ask for a transaction lookup for this address.'}</div>}
      <div className="pattern-summary"><strong>Analysis scope:</strong> These are fetched transactions. No individual suspicious/normal classification is available; transaction execution success does not indicate safety.</div>
    </> : <>
      <h3>{assessment?.label === 'scam' ? 'Why was this flagged?' : 'What does the evidence show?'}</h3>
      <p className="lookup-caption">Evidence recorded by {assessment?.source || 'the detector'}. Missing data is a limitation, rather than a scam indicator.</p>
      <div className={`evidence-cards ${assessment?.label || ''}`}>{assessment?.evidence.map((item, index) => <div className="evidence-card" key={index}><span className="evidence-icon" aria-hidden="true">ⓘ</span><div><h4>Evidence {String(index + 1).padStart(2, '0')}</h4><p>{item.description}</p></div></div>)}</div>
      {!assessment?.evidence.length && <div className="lookup-empty">The detector did not provide supporting evidence items for this assessment.</div>}
    </>}
  </section>
}
