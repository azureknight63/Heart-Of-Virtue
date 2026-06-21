/**
 * Portrait resolution for the staged conversation (event dialogue) feature.
 *
 * Portraits live at `/assets/portraits/<speaker-slug>/<emotion>.png` by
 * convention. Jean ships real emotion art; any other speaker (or a missing
 * emotion file) falls back to a generic placeholder via the image `onError`
 * handler, so the engine stays art-agnostic and new characters render
 * immediately without code changes.
 */

export const PLACEHOLDER_PORTRAIT = '/assets/portraits/_placeholder.png'

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
    return `/assets/portraits/${slug}/${normalizeEmotion(emotion)}.png`
}

/** Shared `onError` handler: swap a failed portrait to the placeholder once. */
export function handlePortraitError(e) {
    const img = e?.currentTarget
    if (!img || img.dataset.fallback === '1') return
    img.dataset.fallback = '1'
    img.src = PLACEHOLDER_PORTRAIT
}
