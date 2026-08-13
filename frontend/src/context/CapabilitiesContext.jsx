import React, { createContext, useContext, useEffect, useState } from 'react';
import apiEndpoints from '../api/endpoints';

/**
 * Backend-owned runtime capability discovery (issue #436, hardened in #496).
 *
 * Split out of AuthContext: capability discovery is not an auth concern, and
 * coupling it to auth forced every consumer (GamePage, its tests) to mock
 * authentication just to read a streaming flag. This context owns the single
 * `/api/info` fetch and exposes the derived capabilities to whoever needs them.
 */
const CapabilitiesContext = createContext();

/** True only when the backend explicitly reports the capability as on. Any
 * other shape (missing, false, discovery failure) resolves to disabled — the
 * safe default while HTTP combat state stays authoritative. */
export const isCombatSocketStreamingEnabled = (capabilities) =>
  capabilities?.combat_socket_streaming === true;

// Module-level so every mounted CapabilitiesProvider — including the two
// mounts React StrictMode produces in development — awaits the same request
// instead of firing one apiece.
let discoveryPromise = null;

function discoverCapabilities() {
  if (!discoveryPromise) {
    discoveryPromise = apiEndpoints.app.getInfo()
      .then((response) => response.data.features || {})
      .catch((error) => {
        // console.warn is the project's existing observability boundary for
        // this class of failure (see utils/logger.js, which ships console.*
        // calls to the backend in dev) — the safe fallback below still applies
        // regardless of whether anything is listening.
        console.warn('Runtime capability discovery failed; capability-gated features stay disabled', error);
        return {};
      });
  }
  return discoveryPromise;
}

/** Test-only: clears the cached discovery so the next provider mount re-fetches. */
export function _resetCapabilitiesCache() {
  discoveryPromise = null;
}

export const useCapabilities = () => {
  const context = useContext(CapabilitiesContext);
  if (!context) {
    throw new Error('useCapabilities must be used within a CapabilitiesProvider');
  }
  return context;
};

export const CapabilitiesProvider = ({ children }) => {
  const [capabilities, setCapabilities] = useState(null);

  useEffect(() => {
    let cancelled = false;
    discoverCapabilities().then((features) => {
      if (!cancelled) setCapabilities(features);
    });
    return () => { cancelled = true; };
  }, []);

  const value = {
    // null until the first /api/info response lands (or fails and falls back
    // to {}) — callers that need to wait for a settled answer (e.g. gating
    // the game surface, issue #496 item 7) read this instead of guessing
    // from combatSocketStreaming alone.
    capabilitiesLoading: capabilities === null,
    combatSocketStreaming: isCombatSocketStreamingEnabled(capabilities),
  };

  return (
    <CapabilitiesContext.Provider value={value}>
      {children}
    </CapabilitiesContext.Provider>
  );
};
