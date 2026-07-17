// Curated, UI-facing subset of the root CHANGELOG.md — condensed to short
// highlights for display in the login screen's changelog panel. Update this
// alongside CHANGELOG.md when cutting a new version; newest entry first.
export const CHANGELOG = [
  {
    version: '0.1.0.0',
    date: '2026-04-30',
    highlights: [
      'Mobile support: Heart of Virtue is now playable on phones',
      'Collapsible room descriptions on mobile and desktop',
      'Touch target and viewport fixes across the mobile UI',
    ],
  },
  {
    version: '0.0.6.0',
    date: '2026-04-17',
    highlights: [
      'Fixed a stray paragraph-break marker leaking into event text',
    ],
  },
  {
    version: '0.0.5.1',
    date: '2026-04-14',
    highlights: [
      'Combat: fixed level-up dialog race condition in multi-battle chains',
      'Combat: fixed a crash in the Check move during chained battles',
      'Inventory: fixed the stats panel showing default values',
      'Ch01: fixed a chest battle event that could fire prematurely',
    ],
  },
  {
    version: '0.0.5.0',
    date: '2026-04-13',
    highlights: [
      'Added the Eastern Descent map (Chapter 3, 35 tiles)',
      'Added TalusHound and ScarpAdder enemies',
      'Added Mara full-combatant upgrade, plus Devet and Liss NPCs',
    ],
  },
  {
    version: '0.0.4.1',
    date: '2026-04-03',
    highlights: [
      'Fixed a delay showing the Event Dialog after post-combat events',
      'Fixed 14 Dark Grotto map bugs',
      'Security: patched a critical axios vulnerability',
    ],
  },
]
