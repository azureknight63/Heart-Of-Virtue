/**
 * Runtime capability helpers (issue #436).
 *
 * combatSocketEnabled reads the backend-owned COMBAT_SOCKET_STREAMING
 * capability. When enabled, combat animations/SFX/state are driven by the
 * engine's beat stream over Socket.IO instead of the lump-response replay.
 */
export function combatSocketEnabled(capability) {
  return capability?.combat_socket_streaming === true;
}
