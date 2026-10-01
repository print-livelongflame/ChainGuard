import { useEffect, useRef, useState } from 'react'
import type { Chat, InputAttachment } from '../api'
import Brand from '../components/Brand'

const suggestions = [
  { title: 'Wallet Risk', description: 'Check a wallet for suspicious activity', prompt: 'Check this wallet for scam activity: [enter a complete Ethereum address]' },
  { title: 'Token Security', description: 'Take a closer look at an ERC-20 token', prompt: 'Check the security of this token contract: [enter a complete Ethereum contract address]' },
  { title: 'Risk Indicators', description: 'Understand why a contract may be flagged', prompt: 'Explain the risk indicators for this contract: [enter a complete Ethereum contract address]' },
  { title: 'Educational', description: 'Learn how blockchain scams work', prompt: 'What is a blockchain rug pull, and what warning signs should I look for?' },
]

type Props = {
  chat: Chat | undefined; draft: string; disabled: boolean
  onDraft: (value: string) => void; onSend: (attachment?: InputAttachment) => Promise<boolean>
}

export default function ChatPage({ chat, draft, disabled, onDraft, onSend }: Props) {
  const end = useRef<HTMLDivElement>(null)
  const composer = useRef<HTMLTextAreaElement>(null)
  const filePicker = useRef<HTMLInputElement>(null)
  const [attachment, setAttachment] = useState<InputAttachment | null>(null)
  const [fileError, setFileError] = useState('')
  const empty = !chat?.messages.length
  useEffect(() => { end.current?.scrollIntoView({ behavior: 'smooth', block: 'end' }) }, [chat?.id, chat?.messages.length, chat?.processing])

  async function chooseFile(file?: File) {
    setFileError('')
    if (!file) return
    if (!/\.(txt|json)$/i.test(file.name)) {
      setFileError('Choose a .txt or .json file.')
      return
    }
    if (file.size > 50 * 1024) {
      setFileError('Files must be 50 KB or smaller.')
      return
    }
    try {
      const content = await file.text()
      if (file.name.toLowerCase().endsWith('.json')) JSON.parse(content)
      setAttachment({ name: file.name, content })
    } catch {
      setFileError('Could not read the file. JSON files must contain valid JSON.')
    }
  }

  async function submit() {
    if (disabled || (!draft.trim() && !attachment)) return
    if (await onSend(attachment ?? undefined)) setAttachment(null)
  }

  return <>
    <div className={`transcript ${empty ? 'empty-transcript' : ''}`}>
      {empty ? <section className="welcome">
        <div className="welcome-emblem"><Brand /></div>
        <h1>How can ChainGuard help?</h1>
        <p>Analyse wallets, transactions and tokens for potential blockchain scams.</p>
        <div className="suggestions">{suggestions.map(item => <button key={item.title} onClick={() => { onDraft(item.prompt); composer.current?.focus() }}>
          <strong>{item.title}</strong><span>{item.description}</span>
        </button>)}</div>
      </section> : <div className="messages" role="log" aria-label="Conversation" aria-live="polite">
        {chat.messages.map(message => <article className={`message ${message.role}`} key={message.id}>
          <div className="message-avatar">{message.role === 'assistant' ? <Brand /> : <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden="true"><circle cx="12" cy="8" r="3"/><path d="M6 20v-3a6 6 0 0 1 12 0v3"/></svg>}</div>
          <div className="message-content"><h2>{message.role === 'user' ? 'You' : 'ChainGuard AI'}</h2><div className="message-text">{message.text}</div>
            {message.attachments.map(file => file.url
              ? <a className="attachment" key={file.id} href={file.url} download={file.name}><span aria-hidden="true">↓</span> Download {file.name}</a>
              : <span className="attachment" key={file.id}><span aria-hidden="true">▤</span> {file.name} included</span>)}
          </div>
        </article>)}
        {chat.processing && <div className="message assistant" role="status"><div className="message-avatar"><Brand /></div><div className="message-content"><h2>ChainGuard AI</h2><p className="thinking"><span />Thinking…</p></div></div>}
      </div>}
      <div ref={end} />
    </div>
    <div className="composer-area">
      {attachment && <div className="pending-attachment"><span aria-hidden="true">▤</span><span>{attachment.name}</span><button type="button" onClick={() => setAttachment(null)} aria-label="Remove attachment">×</button></div>}
      {fileError && <p className="file-error" role="alert">{fileError}</p>}
      <form className="composer" onSubmit={event => { event.preventDefault(); void submit() }}>
      <label className="sr-only" htmlFor="message">Message ChainGuard</label>
      <textarea ref={composer} id="message" value={draft} maxLength={12000} rows={2} onChange={event => onDraft(event.target.value)} placeholder="Ask about a wallet, transaction, token or blockchain scam…" onKeyDown={event => {
        if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) { event.preventDefault(); void submit() }
      }} />
      <input ref={filePicker} className="sr-only" type="file" accept=".txt,.json,text/plain,application/json" onChange={event => { void chooseFile(event.target.files?.[0]); event.currentTarget.value = '' }} />
      <button className="attach-button" type="button" disabled={disabled} onClick={() => filePicker.current?.click()} aria-label="Attach a text or JSON file" title="Attach .txt or .json"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" aria-hidden="true"><path d="m20.5 11.5-8.8 8.8a6 6 0 0 1-8.5-8.5l9.2-9.2a4 4 0 0 1 5.7 5.7l-9.2 9.2a2 2 0 0 1-2.8-2.8l8.5-8.5"/></svg></button>
      <button className="send-button gradient-button" type="submit" disabled={disabled || (!draft.trim() && !attachment)} aria-label="Send message"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true"><path d="M5 12h14m-6-6 6 6-6 6"/></svg></button>
      </form>
    </div>
  </>
}
