import { useEffect, useMemo, useRef, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import axios from 'axios'
import {
  AlertCircle,
  Check,
  CheckCircle,
  Clipboard,
  ExternalLink,
  Loader2,
  LogOut,
  RefreshCw,
  ShieldCheck,
  X,
} from 'lucide-react'
import {
  settingsApi,
  type CodexLogin,
  type CodexModelOption,
  type CodexStatus,
} from '../api/client'

export type CodexLoginPrompt = CodexLogin

interface DisplayCodexModel extends CodexModelOption {
  missing: boolean
}

interface CodexSettingsProps {
  model: string
  onModelChange: (model: string) => void
  savingModel: boolean
}

const CODEX_STATUS_QUERY_KEY = ['settings', 'codex', 'status'] as const
const CODEX_MODELS_QUERY_KEY = ['settings', 'codex', 'models'] as const

export function isTrustedCodexVerificationUrl(value: string): boolean {
  try {
    const url = new URL(value)
    return url.origin === 'https://auth.openai.com'
  } catch {
    return false
  }
}

export function isCodexStatusFresh(
  statusUpdatedAt: number,
  statusVersionAtLogin: number,
): boolean {
  return statusUpdatedAt > statusVersionAtLogin
}

export function shouldClearCodexLoginPrompt(
  prompt: CodexLoginPrompt | null,
  hasFreshStatus: boolean,
  status?: CodexStatus,
): boolean {
  if (!prompt || !hasFreshStatus || !status) return false
  return status.connected || Boolean(status.error) || !status.login_pending
}

export function buildCodexModelOptions(
  models: CodexModelOption[],
  selected: string,
): DisplayCodexModel[] {
  const options = models.map((model) => ({ ...model, missing: false }))
  if (selected && !models.some((model) => model.id === selected)) {
    options.unshift({
      id: selected,
      name: `${selected} (currently selected)`,
      missing: true,
    })
  }
  return options
}

function getApiError(error: unknown, fallback: string): string {
  if (axios.isAxiosError(error)) {
    const detail = error.response?.data?.detail
    if (typeof detail === 'string' && detail.trim()) return detail
  }
  if (error instanceof Error && error.message) return error.message
  return fallback
}

export default function CodexSettings({
  model,
  onModelChange,
  savingModel,
}: CodexSettingsProps) {
  const queryClient = useQueryClient()
  const [loginPrompt, setLoginPrompt] = useState<CodexLoginPrompt | null>(null)
  const [action, setAction] = useState<'login' | 'cancel' | 'logout' | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)
  const [copied, setCopied] = useState(false)
  const actionLockRef = useRef(false)
  const statusVersionAtLoginRef = useRef(0)

  const statusQuery = useQuery({
    queryKey: CODEX_STATUS_QUERY_KEY,
    queryFn: settingsApi.getCodexStatus,
    retry: 1,
    refetchInterval: (query) => (
      query.state.data?.login_pending || loginPrompt ? 1500 : false
    ),
  })

  const status = statusQuery.data
  const hasFreshLoginStatus = isCodexStatusFresh(
    statusQuery.dataUpdatedAt,
    statusVersionAtLoginRef.current,
  )

  const modelsQuery = useQuery({
    queryKey: CODEX_MODELS_QUERY_KEY,
    queryFn: settingsApi.getCodexModels,
    enabled: Boolean(status?.connected),
    retry: 1,
  })

  const modelOptions = useMemo(
    () => buildCodexModelOptions(modelsQuery.data ?? [], model),
    [modelsQuery.data, model],
  )

  useEffect(() => {
    if (!shouldClearCodexLoginPrompt(loginPrompt, hasFreshLoginStatus, status)) return

    setLoginPrompt(null)
    setCopied(false)
    if (status && !status.connected && !status.error) {
      setActionError('Sign-in ended before the Codex account was connected.')
    }
  }, [hasFreshLoginStatus, loginPrompt, status])

  const runLockedAction = async (
    nextAction: 'login' | 'cancel' | 'logout',
    operation: () => Promise<void>,
  ) => {
    if (actionLockRef.current) return
    actionLockRef.current = true
    setAction(nextAction)
    setActionError(null)
    try {
      await operation()
    } catch (error) {
      if (nextAction === 'login') {
        setLoginPrompt(null)
        setCopied(false)
      }
      setActionError(getApiError(error, `Could not ${nextAction} Codex.`))
    } finally {
      actionLockRef.current = false
      setAction(null)
    }
  }

  const startLogin = () => runLockedAction('login', async () => {
    setLoginPrompt(null)
    setCopied(false)
    await queryClient.cancelQueries({ queryKey: CODEX_STATUS_QUERY_KEY, exact: true })
    statusVersionAtLoginRef.current = queryClient.getQueryState(CODEX_STATUS_QUERY_KEY)?.dataUpdatedAt ?? 0
    const login = await settingsApi.startCodexLogin()
    setLoginPrompt(login)
    queryClient.setQueryData<CodexStatus>(CODEX_STATUS_QUERY_KEY, (current) => ({
      available: current?.available ?? true,
      connected: false,
      plan_type: null,
      login_pending: true,
      error: null,
    }))
    await statusQuery.refetch()
  })

  const cancelLogin = () => runLockedAction('cancel', async () => {
    await queryClient.cancelQueries({ queryKey: CODEX_STATUS_QUERY_KEY, exact: true })
    await settingsApi.cancelCodexLogin()
    setLoginPrompt(null)
    setCopied(false)
    queryClient.setQueryData<CodexStatus>(CODEX_STATUS_QUERY_KEY, (current) => ({
      available: current?.available ?? true,
      connected: false,
      plan_type: null,
      login_pending: false,
      error: null,
    }))
    await statusQuery.refetch()
  })

  const logout = () => runLockedAction('logout', async () => {
    await Promise.all([
      queryClient.cancelQueries({ queryKey: CODEX_STATUS_QUERY_KEY, exact: true }),
      queryClient.cancelQueries({ queryKey: CODEX_MODELS_QUERY_KEY, exact: true }),
    ])
    await settingsApi.logoutCodex()
    setLoginPrompt(null)
    setCopied(false)
    queryClient.setQueryData<CodexStatus>(CODEX_STATUS_QUERY_KEY, (current) => ({
      available: current?.available ?? true,
      connected: false,
      plan_type: null,
      login_pending: false,
      error: null,
    }))
    queryClient.removeQueries({ queryKey: CODEX_MODELS_QUERY_KEY })
    await statusQuery.refetch()
  })

  const copyCode = async () => {
    if (!loginPrompt) return
    try {
      await navigator.clipboard.writeText(loginPrompt.user_code)
      setCopied(true)
      window.setTimeout(() => setCopied(false), 1500)
    } catch {
      setActionError('Could not copy the code. Select it and copy it manually.')
    }
  }

  const queryError = statusQuery.error
    ? getApiError(statusQuery.error, 'Could not load Codex connection status.')
    : null
  const modelsError = modelsQuery.error
    ? getApiError(modelsQuery.error, 'Could not load Codex models.')
    : null
  const busy = action !== null

  if (statusQuery.isLoading) {
    return (
      <div className="flex items-center gap-2 py-6 text-sm text-augustus-400">
        <Loader2 className="h-4 w-4 animate-spin text-accent" />
        Checking Codex availability…
      </div>
    )
  }

  return (
    <div className="space-y-5">
      <div className="rounded-lg border border-augustus-700 bg-augustus-950/40 p-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <div className="flex items-center gap-2">
              <ShieldCheck className="h-5 w-5 text-accent" />
              <h3 className="font-medium text-white">ChatGPT account connection</h3>
            </div>
            <p className="mt-2 max-w-2xl text-xs leading-5 text-augustus-400 sm:text-sm">
              Augustus uses a managed Codex sign-in that is separate from any Codex desktop or CLI
              credentials already on this computer. Generation uses your ChatGPT subscription
              allowance. Text-to-speech remains configured separately below.
            </p>
          </div>

          {status?.connected && (
            <span className="inline-flex items-center gap-1.5 rounded-full bg-green-500/20 px-2.5 py-1 text-xs text-green-400">
              <CheckCircle className="h-3.5 w-3.5" />
              Connected{status.plan_type ? ` · ${status.plan_type}` : ''}
            </span>
          )}
        </div>

        {status && !status.available && (
          <div className="mt-4 rounded-lg border border-yellow-500/30 bg-yellow-500/10 p-3 text-sm text-yellow-200">
            <div className="flex items-start gap-2">
              <AlertCircle className="mt-0.5 h-4 w-4 flex-shrink-0" />
              <div>
                <p className="font-medium">Codex CLI is unavailable on the backend host.</p>
                <p className="mt-1 text-xs text-yellow-200/80">
                  Install it there with <code className="rounded bg-black/20 px-1 py-0.5">npm install -g @openai/codex</code>, then refresh this status.
                </p>
              </div>
            </div>
          </div>
        )}

        {(queryError || status?.error || actionError) && (
          <div className="mt-4 flex items-start gap-2 rounded-lg border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-300" role="alert">
            <AlertCircle className="mt-0.5 h-4 w-4 flex-shrink-0" />
            <span>{actionError || status?.error || queryError}</span>
          </div>
        )}

        {loginPrompt && (status?.login_pending || !hasFreshLoginStatus) && (
          <div className="mt-4 rounded-lg border border-accent/40 bg-accent/10 p-4">
            <p className="font-medium text-white">Finish sign-in with this one-time code</p>
            <div className="mt-3 flex flex-col gap-3 sm:flex-row sm:items-center">
              <button
                type="button"
                onClick={copyCode}
                className="flex min-h-[48px] flex-1 items-center justify-between rounded-lg border border-augustus-600 bg-augustus-900 px-4 font-mono text-lg font-semibold tracking-[0.14em] text-white hover:border-augustus-500"
                title="Copy device code"
              >
                <span>{loginPrompt.user_code}</span>
                {copied ? <Check className="h-4 w-4 text-green-400" /> : <Clipboard className="h-4 w-4 text-augustus-400" />}
              </button>

              {isTrustedCodexVerificationUrl(loginPrompt.verification_url) ? (
                <a
                  href={loginPrompt.verification_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="btn btn-primary gap-2 whitespace-nowrap"
                >
                  Open OpenAI sign-in
                  <ExternalLink className="h-4 w-4" />
                </a>
              ) : (
                <span className="text-xs text-red-300">The server returned an invalid sign-in URL.</span>
              )}
            </div>
            <div className="mt-3 flex flex-wrap items-center justify-between gap-3">
              <span className="inline-flex items-center gap-2 text-xs text-augustus-400">
                <Loader2 className="h-3.5 w-3.5 animate-spin text-accent" />
                Waiting for authorization…
              </span>
              <button
                type="button"
                onClick={cancelLogin}
                disabled={busy}
                className="inline-flex min-h-[36px] items-center gap-1.5 rounded-lg px-3 text-xs font-medium text-augustus-300 hover:bg-augustus-800 hover:text-white disabled:opacity-50"
              >
                {action === 'cancel' ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <X className="h-3.5 w-3.5" />}
                Cancel sign-in
              </button>
            </div>
          </div>
        )}

        <div className="mt-4 flex flex-wrap items-center gap-3">
          {status?.connected ? (
            <button
              type="button"
              onClick={logout}
              disabled={busy}
              className="btn btn-secondary gap-2"
            >
              {action === 'logout' ? <Loader2 className="h-4 w-4 animate-spin" /> : <LogOut className="h-4 w-4" />}
              Disconnect
            </button>
          ) : status?.login_pending && !loginPrompt ? (
            <button
              type="button"
              onClick={cancelLogin}
              disabled={busy}
              className="btn btn-secondary gap-2"
            >
              {action === 'cancel' ? <Loader2 className="h-4 w-4 animate-spin" /> : <X className="h-4 w-4" />}
              Cancel pending sign-in
            </button>
          ) : !loginPrompt && (
            <button
              type="button"
              onClick={startLogin}
              disabled={!status?.available || busy || status?.login_pending}
              className="btn btn-primary gap-2"
            >
              {action === 'login' ? <Loader2 className="h-4 w-4 animate-spin" /> : <ShieldCheck className="h-4 w-4" />}
              Connect ChatGPT
            </button>
          )}

          <button
            type="button"
            onClick={() => statusQuery.refetch()}
            disabled={statusQuery.isFetching || busy}
            className="inline-flex min-h-[44px] items-center gap-2 rounded-lg px-3 text-sm text-augustus-400 hover:bg-augustus-800 hover:text-white disabled:opacity-50"
          >
            <RefreshCw className={`h-4 w-4 ${statusQuery.isFetching ? 'animate-spin' : ''}`} />
            Refresh status
          </button>
        </div>

        {!status?.connected && (
          <p className="mt-3 text-xs text-augustus-500">
            Device authorization may need to be enabled in your ChatGPT Security settings.{' '}
            <a
              href="https://learn.chatgpt.com/docs/auth"
              target="_blank"
              rel="noopener noreferrer"
              className="text-accent hover:underline"
            >
              see the OpenAI authentication guide
            </a>
            .
          </p>
        )}
      </div>

      {status?.connected && (
        <div>
          <label className="label" htmlFor="codex-model">Codex model</label>
          <p className="mb-2 text-xs text-augustus-500">
            Leave this on the default to let Codex choose the current recommended model.
          </p>
          <select
            id="codex-model"
            value={model}
            onChange={(event) => onModelChange(event.target.value)}
            disabled={modelsQuery.isLoading || savingModel || busy}
            className="input"
          >
            <option value="">Default (recommended)</option>
            {modelOptions.map((option) => (
              <option key={option.id} value={option.id}>
                {option.name}
              </option>
            ))}
          </select>
          {(modelsQuery.isLoading || savingModel) && (
            <span className="mt-2 inline-flex items-center gap-1.5 text-xs text-augustus-500">
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
              {savingModel ? 'Saving model…' : 'Loading models…'}
            </span>
          )}
          {modelsError && (
            <p className="mt-2 text-xs text-red-300" role="alert">{modelsError}</p>
          )}
        </div>
      )}
    </div>
  )
}
