import type { ReactNode } from 'react'

export default function AppLayout({ sidebar, children }: { sidebar: ReactNode; children: ReactNode }) {
  return <div className="app-layout">{sidebar}<main className="main-panel">{children}</main></div>
}
