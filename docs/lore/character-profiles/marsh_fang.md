# Marsh-Fang (Mersh)
## Overview
- Common name: Marsh-Fang (calls himself Mersh among friends)
- Race / type: Marshfolk Broker — an amphibious-adjacent, humanoid people with smooth, damp skin and lithe, webbed fingers. Imagine amphibious physiology adapted for marsh and market.
- Age: Late middle years — weathered, practiced, and quick to judge.
- Occupation: Rumor-runner, broker, and freelance negotiator; frequent companion and confidant to Jambo.

## Appearance & Manner
- Appearance: Damp-sheen skin in muted greens and grays, expressive eyes with a faintly reflective quality, and a mouth that curls in a perpetual, sardonic half-smile. Prefers damp-proof wraps and a bandolier of glass vials and small notes. Moves with catlike economy; when he speaks, his hands trace invisible ledgers.
- Manner: Sardonic, dry, and forever testing people with soft, teasing barbs. He'll publicly harrangue and rib Jambo — theatrical insults, mock outrage — but his barbs are affectionate and protective. In private he becomes measured and precise, offering Jambo market intelligence and social reads.
- Temperament: Pragmatic and cunning beneath the sardonic exterior. Mersh is quick to recognize leverage and opportunity; he prefers solutions that preserve profit and safety over sentimental choices. His cunning is tactical rather than cruel — he calculates risks and maneuvers people gently into safer outcomes when possible.

## Relationship to Jambo
- Long-standing trading ally and de facto intelligence broker. Marsh-Fang and Jambo trade insults in public: Jambo's showmanship is a perfect foil for Mersh's dry retorts. The repartee helps both draw customers and defuse tension; the act masks a deep loyalty and a habit of watching Jambo's back from the shadows.
- Mersh often scouts routes, checks incoming caravans, and returns with gossip and market trends. Jambo supplies potions and a warm booth; Mersh supplies information and tactical discretion.
- Balance with Jambo: Where Mersh's pragmatism looks for leverage, Jambo's trusting idealism and good nature push decisions toward generosity and second chances. Their friendship works because Jambo's optimism keeps Mersh from becoming entirely transactional, and Mersh's cunning keeps Jambo from being taken advantage of. The pair is a functioning tension: Mersh hones the edge; Jambo softens it.

## Role in the Story
- Surface role: A colorful, recurring NPC who spices small-town scenes with wry commentary and market lore. He is the player's window onto local rumors and the subtle social calculus of Grondia and the surrounding region.
- Functional role: Provides "rumor-runner" intel, can size up customers, flag suspicious figures, and unlock low-stakes quests (recover missing supply, broker a quiet deal, discover the origin of a rumor). He can also alter shop interactions by giving targeted advice to Jambo or the player.

## Gameplay Mechanics (suggested)
- Passive Trait — Rumor Runner: When present, increases the shop's chance to receive new rumors or leads (small probabilistic boost per visit). Rumors are short text seeds that can become side-quests or unlock dialog options.
- Active Ability — Posture & Scent Read ("Size 'Em Up"): A short interaction the player or Jambo can request. Returns a concise read (probabilistic) about a customer's likely temperament, means, and intent (e.g., "Likely merchant, tight purse, smooth tongue — 70%" or "Nervous, quick-glancing; could be hiding something — 60%"). Use is limited per shop visit or triggers a cooldown.
- Passive Flavor — Market Whisper: Mersh occasionally leaves the shop to bring back a specific lead (e.g., caravan delay, bounty hunter sighting, or a rare herb on a passing cart). These triggers can spawn short, timed tasks.

## Sample Quests & Hooks
- "The Damp Ledger": A supplier ledger went missing on the marsh road. Mersh suspects foul play; he asks the player to retrieve it quietly. Returns connections to a shady supplier and a small reward.
- "The False Merchant": Mersh spots a traveling merchant passing counterfeit seals. He needs the player to stall the merchant at the stall while he examines the goods and decides whether to expose them publicly or broker a quiet deal.
- "Whispers of Autumn": A rumor of a rare marsh herb surfaces; Mersh wants it for a tincture that would sell well in Jambo's shop. He'll trade leads for favors or a rare coin.

## Dialogue Hooks (public jabs vs private reads)
- Public ribbing (performed in front of customers):
  - "Jambo, your gloss could blind a pilgrim. You selling potions or sunlamps now?"
  - "Careful, friend — if you buy his tonic you'll never have a dull story again. Mostly because you'll be loopy."
- Private insights (quiet, delivered to Jambo or the player):
  - "He breathes like he saw a judge. Either he's guilty or he's about to audition for a tragedy."
  - "Hold your coin — that one’s a silk-finger. Wait until he touches the second shelf. He'll take what he wants when he's sure no one’s watching."

## Personality Beats & Development
- Early: Mersh toys with customers and teases Jambo, presenting as a thorny market fixture who enjoys his standing.
- Middle: Through a small quest (ledger, herb, or counterfeit) the player sees Mersh's competence and quietly heroic choices; the banter reveals purpose rather than performative malice.
- Late: Reveals (optionally) a soft loyalty — a backstory tie to Jambo (saved him from a caravan skirmish) or a personal reason for staying in Grondia.

## Name & Flavor Options
- Common handle: Mersh (Marsh-Fang)
- Formal name options: Mersh'tal, Orin-Mersh, Vess-Marsh
- Nicknames: The Broker, Mersh the Scent, Marsh-Fang

## Implementation notes (dev-friendly)
- Keep active reads explicitly probabilistic and fallible to avoid railroading player choices. Present results as guidance, not absolute truth.
- Tie rumor-generation to existing shop visit logic (small chance per restock/shop-open event) and log rumors in a simple structure (title, short text, seed data) under `src/resources` or a lightweight in-game journal entry so tests can target it.
- Dialogue: implement public jabs as shop ambient lines; private reads as a small dialog branch available via an "Ask Mersh" option while in the shop.

## Brief lyrical snippet
> "Mersh smiled with the slow amusement of something that keeps its best stories in its pocket. He jabbed Jambo's pride like a stick at a sleeping bee — just enough to make it murmur, never break."
