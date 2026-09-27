export default function Sidebar() {
    return (
      <aside className="flex min-h-screen w-64 flex-col border-r border-slate-800 bg-slate-900 p-4">
  
        <div className="mb-8">
          <h1 className="text-xl font-bold">
            ChainGuard
          </h1>
        </div>
  
        <button className="mb-6 rounded-lg bg-blue-600 px-4 py-3 text-left hover:bg-blue-500">
          + New Chat
        </button>
  
        <div className="flex-1">
          <p className="mb-3 text-xs uppercase text-slate-500">
            Recent Analyses
          </p>
  
          <button className="w-full rounded-lg px-3 py-2 text-left hover:bg-slate-800">
            0x742d...44e
          </button>
        </div>
  
        <button className="rounded-lg px-3 py-2 text-left hover:bg-slate-800">
          ⚙ Settings
        </button>
  
      </aside>
    );
  }