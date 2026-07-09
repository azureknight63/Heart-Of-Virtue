/**
 * Portrait resolution for the staged conversation (event dialogue) feature.
 *
 * Portraits live at `/assets/portraits/<speaker-slug>/<emotion>.png` by
 * convention. On load failure, `handlePortraitError` walks a three-step
 * fallback chain: the tagged emotion image -> that speaker's `neutral.png`
 * -> the generic placeholder. This lets speakers ship partial emotion sets
 * (or none at all) and still render something recognizable before falling
 * back to the art-agnostic placeholder. Callers must set `data-speaker-slug`
 * and `data-emotion` (the normalized emotion) on the `<img>` for the chain
 * to resolve correctly — see `ConversationStage.jsx`.
 */

/**
 * Resolve a public-asset path against the Vite base URL. The app is served
 * under a sub-path (e.g. `/games/HeartOfVirtue/`), so a root-absolute
 * `/assets/...` would 404 in production. Mirrors AudioContext's getAssetPath.
 */
export function assetPath(path) {
    const base = (import.meta.env.BASE_URL || '/').replace(/\/$/, '')
    const clean = path.startsWith('/') ? path : `/${path}`
    return `${base}${clean}`
}

export const PLACEHOLDER_PORTRAIT = assetPath('/assets/portraits/_placeholder.png')

export const EMOTIONS = ['neutral', 'happy', 'sad', 'angry', 'surprised', 'skeptical']

/** Normalize a speaker id/name into a filesystem-safe folder slug. */
export function speakerSlug(speaker) {
    return String(speaker || '')
        .trim()
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, '-')
        .replace(/^-+|-+$/g, '')
}

/** Coerce an emotion to the known vocabulary, defaulting to 'neutral'. */
export function normalizeEmotion(emotion) {
    const e = String(emotion || 'neutral').trim().toLowerCase()
    return EMOTIONS.includes(e) ? e : 'neutral'
}

/**
 * Resolve the portrait URL for a speaker + emotion. Returns the placeholder
 * directly when there is no speaker; otherwise returns the conventional path
 * (the caller wires `onError` to fall back to the placeholder for speakers
 * without art).
 */
export function portraitUrl(speaker, emotion) {
    const slug = speakerSlug(speaker)
    if (!slug) return PLACEHOLDER_PORTRAIT
    return assetPath(`/assets/portraits/${slug}/${normalizeEmotion(emotion)}.png`)
}

/**
 * Shared `onError` handler: walks the fallback chain step by step.
 *   1. Tagged emotion image failed -> try that speaker's `neutral.png`.
 *   2. `neutral.png` failed (or speaker is unknown) -> generic placeholder.
 *   3. Placeholder failed -> give up (avoid an infinite error loop).
 */
export function handlePortraitError(e) {
    const img = e?.currentTarget
    if (!img) return

    const stage = img.dataset.fallback
    if (stage === 'placeholder') return

    // Skip the neutral step if the tagged emotion was already 'neutral' (its
    // image just 404'd) — comparing `img.src` (the browser-resolved absolute
    // URL) against a freshly-built relative path would never match, causing
    // a redundant re-request of the same broken URL.
    if (!stage && img.dataset.emotion !== 'neutral') {
        const slug = img.dataset.speakerSlug
        if (slug) {
            img.dataset.fallback = 'neutral'
            img.src = assetPath(`/assets/portraits/${slug}/neutral.png`)
            return
        }
    }

    img.dataset.fallback = 'placeholder'
    img.src = PLACEHOLDER_PORTRAIT
}
