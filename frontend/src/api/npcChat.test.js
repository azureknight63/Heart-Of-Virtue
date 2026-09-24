import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import npcChat, { NPC_CHAT_TIMEOUT_MS } from './npcChat';
import apiClient from './client';

// Asserted on every LLM-backed call rather than only once: the deadline is
// what keeps a hung provider from pinning the panel (#618), and a call that
// quietly stopped sending it would look identical from the outside.
const withDeadline = { timeout: NPC_CHAT_TIMEOUT_MS };

vi.mock('./client', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
  }
}));

describe('npcChat', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('opens a conversation', () => {
    npcChat.open('Mynx');
    expect(apiClient.post).toHaveBeenCalledWith(
      '/npc/chat/open',
      { npc_id: 'Mynx' },
      withDeadline
    );
  });

  it('sends a response with the default tone', () => {
    npcChat.respond('npc_session_123', 'Hello there');
    expect(apiClient.post).toHaveBeenCalledWith(
      '/npc/chat/respond',
      {
        npc_key: 'npc_session_123',
        jean_text: 'Hello there',
        jean_tone: 'direct',
      },
      withDeadline
    );
  });

  it('sends a response with an explicit tone', () => {
    npcChat.respond('npc_session_123', 'Back off', 'guarded');
    expect(apiClient.post).toHaveBeenCalledWith(
      '/npc/chat/respond',
      {
        npc_key: 'npc_session_123',
        jean_text: 'Back off',
        jean_tone: 'guarded',
      },
      withDeadline
    );
  });

  it('sends the turn_id that makes a retried turn idempotent (#636)', () => {
    npcChat.respond('npc_session_123', 'Back off', 'guarded', 'turn_0123456789');
    expect(apiClient.post).toHaveBeenCalledWith(
      '/npc/chat/respond',
      {
        npc_key: 'npc_session_123',
        jean_text: 'Back off',
        jean_tone: 'guarded',
        turn_id: 'turn_0123456789',
      },
      withDeadline
    );
  });

  it('bounds a re-send by the deadline the caller has left (#636)', () => {
    npcChat.respond('npc_session_123', 'Back off', 'guarded', 'turn_0123456789', 4200);
    expect(apiClient.post).toHaveBeenCalledWith(
      '/npc/chat/respond',
      expect.objectContaining({ turn_id: 'turn_0123456789' }),
      { timeout: 4200 }
    );
  });

  it('ends a conversation with its open token (#674)', () => {
    npcChat.end('npc_session_123', 'tok_0123456789');
    expect(apiClient.post).toHaveBeenCalledWith(
      '/npc/chat/end',
      { npc_key: 'npc_session_123', open_token: 'tok_0123456789' },
      withDeadline
    );
  });

  it('ends a conversation', () => {
    npcChat.end('npc_session_123');
    expect(apiClient.post).toHaveBeenCalledWith(
      '/npc/chat/end',
      { npc_key: 'npc_session_123' },
      withDeadline
    );
  });

  it('retrieves conversation history', () => {
    npcChat.history('npc_session_123');
    expect(apiClient.get).toHaveBeenCalledWith('/npc/chat/history/npc_session_123');
  });

  describe('the turn deadline (#618)', () => {
    // The outer bound this suite refuses to let the deadline exceed — NOT the
    // constant itself, which npcChat.js derives from the engine's own turn
    // budget. Asserting against the constant would only compare it to itself;
    // what matters to the player is that SOME finite bound exists and that it
    // is nowhere near the 90s+ spinner issue #618 was filed for.
    const ABANDON_AFTER_MS = 120000;

    /**
     * A server that never answers. Stands in for axios' own timeout handling:
     * the returned promise settles only if the request config carries a finite
     * `timeout`, which is exactly the condition under test. Without one the
     * caller waits forever, `phase` stays at WAITING_NPC and the panel's
     * loading state never clears.
     */
    const hangingPost = (_url, _body, config) =>
      new Promise((_resolve, reject) => {
        if (!Number.isFinite(config?.timeout)) return;
        setTimeout(
          () =>
            reject(
              Object.assign(new Error(`timeout of ${config.timeout}ms exceeded`), {
                code: 'ECONNABORTED',
              })
            ),
          config.timeout
        );
      });

    beforeEach(() => {
      vi.useFakeTimers();
      apiClient.post.mockImplementation(hangingPost);
    });

    afterEach(() => {
      vi.useRealTimers();
      apiClient.post.mockReset();
    });

    it.each([
      ['open', () => npcChat.open('Mynx')],
      ['respond', () => npcChat.respond('npc_session_123', 'Hello there')],
      // `/end` carries the same bound. Nothing on screen waits on it (the
      // panel closes first and sends it fire-and-forget), but an unanswered
      // one should still settle and be logged rather than hang.
      ['end', () => npcChat.end('npc_session_123')],
    ])('aborts a /%s the server never answers', async (_label, call) => {
      const settled = vi.fn();
      call().then(settled, settled);

      await vi.advanceTimersByTimeAsync(ABANDON_AFTER_MS);

      expect(settled).toHaveBeenCalledTimes(1);
      // ECONNABORTED is what axios raises on its own timeout, and is the code
      // useNpcChat's failure copy keys the "timed out" branch on.
      expect(settled.mock.calls[0][0]).toMatchObject({ code: 'ECONNABORTED' });
    });
  });
});
