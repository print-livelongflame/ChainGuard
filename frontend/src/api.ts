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

export type LLMProvider = 'openai' | 'claude' | 'gemini' | 'local'
export type AgentAssignments = Record<'business_analyser' | 'scam_checker' | 'forensic_investigator', LLMProvider>
export type LocalLLM = {
  enabled: boolean; name: string; base_url: string; model: string; timeout_seconds: number
  api_key_configured: boolean; connected: boolean; connection_error: string | null
}
export type PromptStrategy = 'zero_shot' | 'chain_of_thought' | 'few_shot'
export type AgentTuning = { prompt_strategy: PromptStrategy; temperature: number }
export type AgentSettings = Record<keyof AgentAssignments, AgentTuning>
export type AgentTokenLimits = Record<keyof AgentAssignments, number | null>
export type LLMSettings = { assignments: AgentAssignments; agents: AgentSettings; token_limits: AgentTokenLimits; local: LocalLLM }

export type AnalysisResult = {
  label: 'scam' | 'not_scam' | 'insufficient_evidence'
  risk_type: string; confidence: number; source: string; address: string | null
  evidence: { description: string; weight: number }[]
  explanation?: string | null
}

export type LookupView = {
  kind: 'transactions' | 'evidence'
  address: string | null; chain: string; queried_at: string | null
  transactions: { hash?: string | null; method?: string | null; value?: string | null; timestamp?: string | number | null; execution_status?: string }[]
  provenance: { status?: string; error?: string; fetched_at?: string }
}

export type Message = {
  id: string; role: 'user' | 'assistant'; text: string; created_at: string
  attachments: Attachment[]
  assessment?: AnalysisResult | null
  lookup?: LookupView | null
  token_usage?: { input_tokens: number; output_tokens: number; total_tokens: number } | null
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
    const detail = Array.isArray(data.detail)
      ? data.detail.map((item: { loc?: string[]; msg?: string }) => `${item.loc?.slice(1).join('.') || 'Request'}: ${item.msg || 'Invalid value'}`).join('; ')
      : typeof data.detail === 'string' ? data.detail : 'The request could not be completed.'
    throw new ApiError(detail, response.status)
  }
  return response.json() as Promise<T>
}

export type AuthSession = {
  authenticated: boolean
  role: 'user' | 'admin' | null
  username: string | null
}
