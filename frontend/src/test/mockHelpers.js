export const combatDisabledAuth = Object.freeze({
  combatSocketStreaming: false,
})

export const capabilitiesApiMock = (vi) => ({
  app: {
    getInfo: vi.fn().mockResolvedValue({ data: { features: {} } }),
  },
})
