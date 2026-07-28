/**
 * Frontend feature flags (issue #436).
 *
 * combatSocketEnabled — mirrors the backend COMBAT_SOCKET_STREAMING flag. When
 * on, combat animations/SFX/state are driven by the engine's beat stream over
 * SocketIO instead of the lump-response replay. Off by default.
 */
export function combatSocketEnabled() {
  const v = import.meta.env.VITE_COMBAT_SOCKET;
  return v === '1' || v === 'true' || v === true;
}
