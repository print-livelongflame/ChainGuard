import { useCallback, useEffect, useRef, useState } from 'react'
import { api, ApiError } from './api'
import type { Chat, ChatList, InputAttachment } from './api'
import AppLayout from './layouts/AppLayout'
import Sidebar from './components/Sidebar'
import ChatPage from './pages/ChatPage'

const SELECTION_KEY = 'chainguard.activeChat'

function App() {
  const [chats, setChats] = useState<Chat[]>([])
  const [selected, setSelected] = useState<string | null>(null)
  const [provider, setProvider] = useState('Connecting…')
  const [drafts, setDrafts] = useState<Record<string, string>>({})
  const [notice, setNotice] = useState('')
  const [configurationError, setConfigurationError] = useState<string | null>(null)
  const [ready, setReady] = useState(false)
  const [creating, setCreating] = useState(false)
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const submitting = useRef(new Set<string>())
  const creatingRef = useRef(false)
  const uncertain = useRef(new Map<string, { text: string; count: number }>())

  const select = useCallback((id: string | null) => {
    setSelected(id)
    if (id) localStorage.setItem(SELECTION_KEY, id)
    else localStorage.removeItem(SELECTION_KEY)
    setSidebarOpen(false)
  }, [])

  const restore = useCallback(async () => {
    try {
      const result = await api<ChatList>('/chats')
      setChats(result.chats)
      setProvider(result.provider)
      setConfigurationError(result.configuration_error)
      const previous = localStorage.getItem(SELECTION_KEY)
      const exists = result.chats.some(chat => chat.id === previous)
      setNotice(previous && !exists ? 'Your previous chat session expired. Start a new conversation.' : '')
      select(exists ? previous : result.chats[0]?.id ?? null)
      setReady(true)
    } catch {
      setNotice('Cannot connect to ChainGuard. Start the backend, then reconnect.')
      setReady(false)
    }
  }, [select])

  useEffect(() => {
    // Defer startup so StrictMode's setup/cleanup probe cannot create two sessions.
    const timer = window.setTimeout(() => { void restore() }, 0)
    return () => window.clearTimeout(timer)
  }, [restore])

  const updateChat = useCallback((updated: Chat) => {
    setChats(current => current.map(chat => chat.id === updated.id && updated.messages.length >= chat.messages.length ? updated : chat))
  }, [])

  const pending = chats.filter(chat => chat.processing).map(chat => chat.id).join(',')
  useEffect(() => {
    if (!pending) return
    let disposed = false
    let running = false
    const timer = window.setInterval(async () => {
      if (running) return
      running = true
      try {
        await Promise.all(pending.split(',').map(async id => {
          try {
            const chat = await api<Chat>(`/chats/${id}`)
            if (!disposed) {
              const submission = uncertain.current.get(id)
              if (submission) {
                uncertain.current.delete(id)
                setChats(current => current.map(item => item.id === id ? chat : item))
                if (chat.messages.length === submission.count) {
                  setDrafts(current => ({ ...current, [id]: current[id] || submission.text }))
                  setNotice('Your message was not received. You can send it again.')
                } else setNotice('')
              } else updateChat(chat)
            }
          } catch (error) {
            if (!disposed) {
              if (error instanceof ApiError && error.status === 404) await restore()
              else setNotice('Connection interrupted. Checking for your reply; your message will not be resent.')
            }
          }
        }))
      } finally { running = false }
    }, 1500)
    return () => { disposed = true; window.clearInterval(timer) }
  }, [pending, restore, updateChat])

  async function newChat() {
    if (creatingRef.current) return
    creatingRef.current = true
    setCreating(true)
    try {
      const chat = await api<Chat>('/chats', {})
      setChats(current => [chat, ...current])
      select(chat.id)
      setNotice('')
      return chat
    } catch { setNotice('Could not create a chat. Check the connection and try again.') }
    finally { creatingRef.current = false; setCreating(false) }
  }

  const active = chats.find(chat => chat.id === selected)
  const draftKey = selected ?? 'welcome'
  const draft = drafts[draftKey] ?? ''

  async function send(attachment?: InputAttachment): Promise<boolean> {
    const text = draft.trim()
    const originKey = draftKey
    if ((!text && !attachment) || !ready || creatingRef.current || active?.processing || configurationError || submitting.current.has(originKey)) return false
    submitting.current.add(originKey)
    let chat = active
    try {
      if (!chat) chat = await newChat()
      if (!chat) return false
      const id = chat.id
      submitting.current.add(id)
      setNotice('')
      setDrafts(current => ({ ...current, [originKey]: '' }))
      updateChat({ ...chat, processing: true, messages: [...chat.messages, {
        id: `pending-${id}`, role: 'user', text, created_at: new Date().toISOString(),
        attachments: attachment ? [{ id: `pending-file-${id}`, name: attachment.name, url: null }] : [],
      }] })
      try {
        updateChat(await api<Chat>(`/chats/${id}/messages`, { text, attachments: attachment ? [attachment] : [] }))
        return true
      } catch (error) {
        uncertain.current.set(id, { text, count: chat.messages.length })
        if (error instanceof ApiError && error.status === 404) {
          await restore()
        } else {
          setNotice(error instanceof ApiError ? error.message : 'Connection interrupted. Checking whether your message was received; it will not be resent.')
          try {
            const actual = await api<Chat>(`/chats/${id}`)
            uncertain.current.delete(id)
            setChats(current => current.map(item => item.id === id ? actual : item))
            if (actual.messages.length === chat.messages.length) setDrafts(current => ({ ...current, [id]: text }))
          } catch { /* Polling keeps checking an uncertain submission. */ }
        }
        return false
      } finally { submitting.current.delete(id) }
    } finally { submitting.current.delete(originKey) }
  }

  return <AppLayout sidebar={<Sidebar chats={chats} selected={selected} open={sidebarOpen} creating={creating || !ready} onNew={() => { void newChat() }} onSelect={select} onClose={() => setSidebarOpen(false)} />}>
    <header className="topbar"><button className="mobile-menu icon-button" onClick={() => setSidebarOpen(true)} aria-label="Open navigation" aria-expanded={sidebarOpen} aria-controls="chat-navigation">☰</button><span>ChainGuard Assistant</span><span className="header-divider">/</span><span className="provider">{provider}</span></header>
    {(notice || configurationError) && <div className="notice" role="status"><span>{notice || configurationError}</span><button onClick={() => { void restore() }}>Reconnect</button></div>}
    <ChatPage key={active?.id ?? 'welcome'} chat={active} draft={draft} disabled={!ready || creating || !!active?.processing || !!configurationError} onDraft={value => setDrafts(current => ({ ...current, [draftKey]: value }))} onSend={send} />
  </AppLayout>
}

export default App
