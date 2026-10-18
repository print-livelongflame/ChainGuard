import { Fragment } from 'react'

function inline(text: string) {
  return text.split(/(\*\*[^*]+\*\*|`[^`]+`)/g).map((part, i) => part.startsWith('**') && part.endsWith('**') ? <strong key={i}>{part.slice(2, -2)}</strong> : part.startsWith('`') && part.endsWith('`') ? <code key={i}>{part.slice(1, -1)}</code> : part)
}

// Model output stays React text, including any HTML supplied by the model.
export default function MessageText({ text }: { text: string }) {
  return <div className="message-text formatted-message">{text.split(/\n\s*\n/).map((block, index) => {
    const lines = block.split('\n')
    if (lines.every(line => /^\s*[-*]\s+/.test(line))) return <ul key={index}>{lines.map((line, i) => <li key={i}>{inline(line.replace(/^\s*[-*]\s+/, ''))}</li>)}</ul>
    if (lines.every(line => /^\s*\d+[.)]\s+/.test(line))) return <ol key={index}>{lines.map((line, i) => <li key={i}>{inline(line.replace(/^\s*\d+[.)]\s+/, ''))}</li>)}</ol>
    if (/^#{1,4}\s/.test(block) && lines.length === 1) return <h3 key={index}>{inline(block.replace(/^#{1,4}\s+/, ''))}</h3>
    if (lines.length >= 3 && lines[0].includes('|') && /^\s*\|?\s*:?-{3,}/.test(lines[1])) {
      const cells = (line: string) => line.trim().replace(/^\||\|$/g, '').split('|').map(cell => cell.trim())
      return <div className="message-table-scroll" key={index}><table><thead><tr>{cells(lines[0]).map((cell, i) => <th key={i}>{inline(cell)}</th>)}</tr></thead><tbody>{lines.slice(2).map((line, i) => <tr key={i}>{cells(line).map((cell, j) => <td key={j}>{inline(cell)}</td>)}</tr>)}</tbody></table></div>
    }
    return <p key={index}>{lines.map((line, i) => <Fragment key={i}>{i > 0 && <br />}{inline(line)}</Fragment>)}</p>
  })}</div>
}
