/**
 * isTypingTarget - true when `target` is a form control a user could be
 * actively typing into (input/textarea/select/contenteditable).
 *
 * A `document`-level keydown listener (the pattern several dialogs use
 * because a focus-trapped ancestor swallows a ref-scoped listener — see
 * BaseDialog's own focus trap, and issue #530) fires for EVERY keydown in
 * the document, not just ones aimed at that dialog. Without this guard, a
 * player typing into an unrelated focused control (a glossary search box,
 * an NPC chat input) can have those keystrokes reinterpreted as the
 * dialog's own shortcuts — e.g. typing "2" into a search field silently
 * submitting a narrative choice (issue found in the code-scrubber pass
 * over issues #530/#541/#539/#529's merged ConversationStage/EventDialog
 * changes). Every document-level keydown listener should bail early when
 * this returns true.
 */
export function isTypingTarget(target) {
  if (!target || !target.tagName) return false
  const tag = target.tagName.toUpperCase()
  return tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT' || target.isContentEditable === true
}

/**
 * isModifiedKeyEvent - true when a keydown carries Ctrl/Cmd/Alt, which
 * usually means the browser or OS owns the shortcut (e.g. Ctrl+2 / Cmd+2
 * switching tabs) rather than the page. A document-level keydown listener
 * that doesn't check this can steal a browser shortcut's keystroke and act
 * on it instead.
 */
export function isModifiedKeyEvent(e) {
  return Boolean(e.ctrlKey || e.metaKey || e.altKey)
}
