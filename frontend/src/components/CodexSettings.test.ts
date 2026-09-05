import { describe, expect, it } from 'vitest'
import {
  buildCodexModelOptions,
  isCodexStatusFresh,
  isTrustedCodexVerificationUrl,
  shouldClearCodexLoginPrompt,
  type CodexLoginPrompt,
} from './CodexSettings'

const prompt: CodexLoginPrompt = {
  login_id: 'login-1',
  verification_url: 'https://auth.openai.com/device',
  user_code: 'ABCD-EFGH',
}

describe('Codex settings state', () => {
  it('rejects status snapshots from before the current login attempt', () => {
    expect(isCodexStatusFresh(100, 100)).toBe(false)
    expect(isCodexStatusFresh(99, 100)).toBe(false)
    expect(isCodexStatusFresh(101, 100)).toBe(true)
  })

  it('renders only HTTPS device links on the exact OpenAI auth host', () => {
    expect(isTrustedCodexVerificationUrl('https://auth.openai.com/device')).toBe(true)
    expect(isTrustedCodexVerificationUrl('http://auth.openai.com/device')).toBe(false)
    expect(isTrustedCodexVerificationUrl('https://auth.openai.com:444/device')).toBe(false)
    expect(isTrustedCodexVerificationUrl('https://auth.openai.com.evil.example/device')).toBe(false)
    expect(isTrustedCodexVerificationUrl('not a url')).toBe(false)
  })

  it('keeps a login prompt until a fresh status reaches a terminal state', () => {
    expect(shouldClearCodexLoginPrompt(prompt, false, {
      available: true,
      connected: false,
      plan_type: null,
      login_pending: false,
      error: null,
    })).toBe(false)

    expect(shouldClearCodexLoginPrompt(prompt, true, {
      available: true,
      connected: false,
      plan_type: null,
      login_pending: true,
      error: null,
    })).toBe(false)

    expect(shouldClearCodexLoginPrompt(prompt, true, {
      available: true,
      connected: true,
      plan_type: 'Plus',
      login_pending: false,
      error: null,
    })).toBe(true)

    expect(shouldClearCodexLoginPrompt(prompt, true, {
      available: true,
      connected: false,
      plan_type: null,
      login_pending: false,
      error: 'Device code expired',
    })).toBe(true)
  })

  it('keeps a saved model visible when it is absent from the latest model response', () => {
    expect(buildCodexModelOptions([
      { id: 'gpt-5', name: 'GPT-5' },
    ], 'gpt-5-codex')).toEqual([
      { id: 'gpt-5-codex', name: 'gpt-5-codex (currently selected)', missing: true },
      { id: 'gpt-5', name: 'GPT-5', missing: false },
    ])
  })

  it('does not duplicate a selected model already returned by the backend', () => {
    expect(buildCodexModelOptions([
      { id: 'gpt-5', name: 'GPT-5' },
    ], 'gpt-5')).toEqual([
      { id: 'gpt-5', name: 'GPT-5', missing: false },
    ])
  })
})
