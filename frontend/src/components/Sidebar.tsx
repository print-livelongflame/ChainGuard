import type { Chat } from '../api'
import Brand from './Brand'


type Props = {
  authenticated: boolean
  onSignIn: () => void
  isAdmin: boolean
  username: string
  logoutBusy: boolean
  onLogout: () => void
  chats: Chat[]
  selected: string | null
  page: 'chat' | 'settings'
  open: boolean
  creating: boolean

  onNew: () => void
  onSelect: (id: string) => void
  onSettings: () => void
  onClose: () => void
}


export default function Sidebar({
  authenticated,
  onSignIn,
  isAdmin,
  username,
  logoutBusy,
  onLogout,
  chats,
  selected,
  page,
  open,
  creating,
  onNew,
  onSelect,
  onSettings,
  onClose,
}: Props) {

  return (
    <>

      {open && (
        <button
          className="sidebar-backdrop"
          aria-label="Close navigation"
          onClick={onClose}
        />
      )}


      <aside
        id="chat-navigation"
        className={`sidebar ${open ? 'is-open' : ''}`}
        onKeyDown={event => {
          if (event.key === 'Escape') {
            onClose()
          }
        }}
      >

        <div className="brand">
          <Brand />

          <span>
            ChainGuard
          </span>

          <button
            className="mobile-close icon-button"
            onClick={onClose}
            aria-label="Close navigation"
          >
            ×
          </button>
        </div>


        <button
          className="new-chat gradient-button"
          disabled={creating}
          onClick={onNew}
        >
          <span aria-hidden="true">
            ＋
          </span>

          {creating ? 'Creating…' : 'New Chat'}
        </button>


        <h2 className="section-label">
          Recent analysis
        </h2>


        <nav
          className="chat-list"
          aria-label="Recent chats"
        >

          {chats.length === 0 && (
            <p className="no-chats">
              Your conversations will appear here.
            </p>
          )}


          {chats.map(chat => (
            <button
              key={chat.id}
              className={`chat-link ${
                page === 'chat' &&
                selected === chat.id
                  ? 'selected'
                  : ''
              }`}
              aria-current={
                page === 'chat' &&
                selected === chat.id
                  ? 'page'
                  : undefined
              }
              onClick={() => onSelect(chat.id)}
              title={chat.title}
            >

              <svg
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="1.5"
                aria-hidden="true"
              >
                <path d="M20 11.5a8 8 0 0 1-8 8 9 9 0 0 1-3.5-.7L4 20l1.2-4.5a8 8 0 1 1 14.8-4Z" />
              </svg>

              <span>
                {chat.title}
              </span>

              {chat.processing && (
                <i
                  className="chat-dot"
                  aria-label="Processing"
                />
              )}

            </button>
          ))}

        </nav>


        <button className={`settings-nav-button ${page === 'settings' ? 'selected' : ''}`} onClick={onSettings} aria-current={page === 'settings' ? 'page' : undefined}>
          <span aria-hidden="true">⚙</span> Settings
        </button>

        <div className="team">
          <span className="team-avatar">
            {username.slice(0, 2).toUpperCase()}
          </span>

          <div>
            {username}

            <small>
              {isAdmin ? 'Admin' : authenticated ? 'User' : 'Guest'}
            </small>
          </div>
        </div>

        {authenticated ? (
          <button className="settings-nav-button" onClick={onLogout} disabled={logoutBusy}>
            {logoutBusy ? 'Signing out…' : 'Sign out'}
          </button>
        ) : (
          <button className="settings-nav-button" onClick={onSignIn}>
            Sign in
          </button>
        )}
      </aside>
    </>
  )
}