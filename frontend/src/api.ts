export type Attachment = { id: string; name: string; url: string | null }

export type InputAttachment = { name: string; content: string }

export type DetectorSettings = {
  enabled: boolean
  name: string
  endpoint: string
  mode: 'template' | 'generic'
  required_input_type: 'address' | 'address_with_context'
  is_llm_based: boolean
}

export type ApiKeyName =
  | 'OPENAI_API_KEY'
  | 'GEMINI_API_KEY'
  | 'ANTHROPIC_API_KEY'
  | 'CLAUDE_API_KEY'
  | 'ETHERSCAN_API_KEY'
  | 'DETECTOR_API_KEY'

export type ApiKeySettings = {
  configured: Record<ApiKeyName, boolean>
  provider: string
  configuration_error: string | null
}

export type Message = {
  id: string; role: 'user' | 'assistant'; text: string; created_at: string
  attachments: Attachment[]
}

export type Chat = {
  id: string; title: string; created_at: string; messages: Message[]
  processing: boolean; error: string | null
}

export type ChatList = { chats: Chat[]; provider: string; configuration_error: string | null }

export class ApiError extends Error {
  status: number
  constructor(message: string, status: number) {
    super(message)
    this.status = status
  }
}

export async function api<T>(path: string, body?: object): Promise<T> {
  const response = await fetch(`/api${path}`, {
    method: body ? 'POST' : 'GET', credentials: 'same-origin',
    headers: body ? { 'Content-Type': 'application/json' } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  })
  if (!response.ok) {
    const data = await response.json().catch(() => ({}))
    throw new ApiError(typeof data.detail === 'string' ? data.detail : 'The request could not be completed.', response.status)
  }
  return response.json() as Promise<T>
}

export type AuthSession = {
  authenticated: boolean
  role: 'user' | 'admin' | null
  username: string | null
}
