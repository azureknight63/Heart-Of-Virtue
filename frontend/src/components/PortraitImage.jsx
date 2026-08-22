import { useEffect, useRef } from 'react'
import { portraitUrl, handlePortraitError, speakerSlug, normalizeEmotion } from '../utils/portraits'

/**
 * PortraitImage — the single `<img>` that knows how to load a character portrait.
 *
 * Wraps the `utils/portraits` convention (`/assets/portraits/<slug>/<emotion>.png`)
 * together with the three-step fallback chain, so every surface that shows a
 * face — the staged conversation, the chat recap strip, the history transcript —
 * resolves art the same way and degrades the same way.
 *
 * The `dataset.fallback` reset is the load-bearing part: `handlePortraitError`
 * records how far down the chain a node has walked, and that marker must be
 * cleared whenever the src changes to a new emotion. Without it a stale
 * 'neutral'/'placeholder' flag from a previous emotion's failed load
 * short-circuits the chain for the next one. Keying the effect on the node
 * (rather than remounting per emotion) also avoids the flicker a keyed `<img>`
 * caused on every beat that changed a speaker's expression.
 *
 * @param {string} speaker  - character id used for the folder slug
 * @param {string} [name]   - display name for the alt text (defaults to `speaker`)
 * @param {string} emotion  - tagged emotion; normalized for the path, raw in the alt
 */
export default function PortraitImage({ speaker, name, emotion, style, className }) {
    const imgRef = useRef(null)

    useEffect(() => {
        if (imgRef.current) delete imgRef.current.dataset.fallback
    }, [speaker, emotion])

    return (
        <img
            ref={imgRef}
            src={portraitUrl(speaker, emotion)}
            data-speaker-slug={speakerSlug(speaker)}
            data-emotion={normalizeEmotion(emotion)}
            onError={handlePortraitError}
            alt={`${name || speaker} (${emotion})`}
            draggable={false}
            className={className}
            style={style}
        />
    )
}
