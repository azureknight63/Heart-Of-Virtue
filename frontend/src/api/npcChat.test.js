import { describe, it, expect, vi, beforeEach } from 'vitest';
import npcChat from './npcChat';
import apiClient from './client';

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
    expect(apiClient.post).toHaveBeenCalledWith('/npc/chat/open', { npc_id: 'Mynx' });
  });

  it('sends a response with the default tone', () => {
    npcChat.respond('npc_session_123', 'Hello there');
    expect(apiClient.post).toHaveBeenCalledWith('/npc/chat/respond', {
      npc_key: 'npc_session_123',
      jean_text: 'Hello there',
      jean_tone: 'direct',
    });
  });

  it('sends a response with an explicit tone', () => {
    npcChat.respond('npc_session_123', 'Back off', 'guarded');
    expect(apiClient.post).toHaveBeenCalledWith('/npc/chat/respond', {
      npc_key: 'npc_session_123',
      jean_text: 'Back off',
      jean_tone: 'guarded',
    });
  });

  it('ends a conversation', () => {
    npcChat.end('npc_session_123');
    expect(apiClient.post).toHaveBeenCalledWith('/npc/chat/end', { npc_key: 'npc_session_123' });
  });

  it('retrieves conversation history', () => {
    npcChat.history('npc_session_123');
    expect(apiClient.get).toHaveBeenCalledWith('/npc/chat/history/npc_session_123');
  });
});
