import { useCallback, useEffect, useRef, useState } from 'react'
import { api, ApiError } from './api'
import type { AuthSession, Chat, ChatList, InputAttachment } from './api'
import AppLayout from './layouts/AppLayout'
import Sidebar from './components/Sidebar'
import AdminLogin from './components/AdminLogin'
import ChatPage from './pages/ChatPage'
import SettingsPage from './pages/SettingsPage'

const SELECTION_KEY = 'chainguard.activeChat'
type Page = 'chat' | 'settings'

function App() {
  const [role, setRole] = useState<AuthSession['role']>('user')
  const [checkingAuth, setCheckingAuth] = useState(true)
  const authRevision = useRef(0)
  const isAdmin = role === 'admin'
  const [page, setPage] = useState<Page>('chat')
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
  
    if (id) {
      localStorage.setItem(SELECTION_KEY, id)
    } else {
      localStorage.removeItem(SELECTION_KEY)
    }
  
    setPage('chat')
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

  const handleSessionChange = useCallback((session: AuthSession) => {
    authRevision.current += 1
    setRole(session.role)
    setCheckingAuth(false)
    if (session.role !== 'admin') {
      setPage('chat')
      setSidebarOpen(false)
    }
  }, [])

  useEffect(() => {
    if (!ready) return
    let cancelled = false

    async function checkSession() {
      const revision = authRevision.current
      try {
        const session = await api<AuthSession>('/auth/me')
        if (!cancelled && revision === authRevision.current) {
          handleSessionChange(session)
        }
      } catch {
        if (!cancelled && revision === authRevision.current) {
          handleSessionChange({ role: 'user' })
        }
      }
    }

    void checkSession()
    const onFocus = () => { void checkSession() }
    window.addEventListener('focus', onFocus)
    return () => {
      cancelled = true
      window.removeEventListener('focus', onFocus)
    }
  }, [ready, handleSessionChange])

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

  return (
    <AppLayout
      sidebar={
        <Sidebar
          isAdmin={isAdmin}
          chats={chats}
          selected={selected}
          page={page}
          open={sidebarOpen}
          creating={creating || !ready}
          onNew={() => {
            void newChat()
          }}
          onSelect={select}
          onSettings={() => {
            if (!isAdmin) return
            setPage('settings')
            setSidebarOpen(false)
          }}
          onClose={() => setSidebarOpen(false)}
        />
      }
    >
  
      <AdminLogin
        isAdmin={isAdmin}
        checking={checkingAuth}
        onSessionChange={handleSessionChange}
      />

      <header className="topbar">
        <button
          className="mobile-menu icon-button"
          onClick={() => setSidebarOpen(true)}
          aria-label="Open navigation"
          aria-expanded={sidebarOpen}
          aria-controls="chat-navigation"
        >
          ☰
        </button>
  
        <span>ChainGuard Assistant</span>
  
        <span className="header-divider">/</span>
  
        {page === 'settings' ? (
          <span className="provider">
            Admin Settings / API Configuration
          </span>
        ) : (
          <span className="provider">
            {provider}
          </span>
        )}
      </header>
  
  
      {page === 'chat' && (
        <>
          {(notice || configurationError) && (
            <div
              className="notice"
              role="status"
            >
              <span>
                {notice || configurationError}
              </span>
  
              <button
                onClick={() => {
                  void restore()
                }}
              >
                Reconnect
              </button>
            </div>
          )}
  
          <ChatPage
            key={active?.id ?? 'welcome'}
            chat={active}
            draft={draft}
            disabled={
              !ready ||
              creating ||
              !!active?.processing ||
              !!configurationError
            }
            onDraft={value =>
              setDrafts(current => ({
                ...current,
                [draftKey]: value,
              }))
            }
            onSend={send}
          />
        </>
      )}
  
  
      {page === 'settings' && isAdmin && (
        <SettingsPage
          provider={provider}
          onApiKeysSaved={settings => {
            setProvider(settings.provider)
            setConfigurationError(settings.configuration_error)
          }}
        />
      )}
  
    </AppLayout>
  )
  }

export default App
