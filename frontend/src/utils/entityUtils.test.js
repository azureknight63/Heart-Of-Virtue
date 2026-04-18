import { describe, it, expect } from 'vitest'
import { cleanTerminalLineBreaks } from './entityUtils'

describe('cleanTerminalLineBreaks', () => {
    it('returns falsy input unchanged', () => {
        expect(cleanTerminalLineBreaks('')).toBe('')
        expect(cleanTerminalLineBreaks(null)).toBe(null)
        expect(cleanTerminalLineBreaks(undefined)).toBe(undefined)
    })

    it('converts single newlines to spaces within a paragraph', () => {
        const input = 'Line one\nLine two\nLine three'
        expect(cleanTerminalLineBreaks(input)).toBe('Line one Line two Line three')
    })

    it('preserves double-newline paragraph breaks', () => {
        const input = 'Para one\n\nPara two'
        expect(cleanTerminalLineBreaks(input)).toBe('Para one\n\nPara two')
    })

    it('preserves 3+ consecutive newlines as a single paragraph break', () => {
        const input = 'Para one\n\n\nPara two'
        expect(cleanTerminalLineBreaks(input)).toBe('Para one\n\nPara two')
    })

    it('handles multiple paragraphs each with internal line breaks', () => {
        const input = 'Para one\nline two\n\nPara two\nline two'
        expect(cleanTerminalLineBreaks(input)).toBe('Para one line two\n\nPara two line two')
    })

    // Regression: the original implementation produced literal ~~~PARA_BREAK~~~ in output
    it('REGRESSION: never leaks ~~~PARA_BREAK~~~ marker into output', () => {
        const input = 'For a moment, there is only silence...\n\nThe smell of old parchment and candle wax.\n\nA woman\'s voice, soft and warm.'
        const result = cleanTerminalLineBreaks(input)
        expect(result).not.toContain('~~~PARA_BREAK~~~')
        expect(result).not.toContain('~~~')
    })

    it('REGRESSION: memory flash multi-paragraph text comes out cleanly', () => {
        // Simulates the exact shape of text that was broken in production
        const input = [
            'For a moment, there is only silence...',
            'The smell of old parchment and candle wax.',
            'A woman\'s voice, soft and warm, reading aloud by firelight.',
            '"Jean, you always were too stubborn for your own good."',
        ].join('\n\n')

        const result = cleanTerminalLineBreaks(input)

        // Each paragraph is preserved, no raw newlines inside a para, no leaking marker
        expect(result).toContain('For a moment, there is only silence...')
        expect(result).toContain('The smell of old parchment and candle wax.')
        expect(result).not.toContain('~~~PARA_BREAK~~~')
        // All inter-paragraph breaks remain as \n\n
        const paragraphs = result.split('\n\n')
        expect(paragraphs.length).toBe(4)
    })

    it('trims leading/trailing whitespace within each paragraph', () => {
        const input = '   Hello\nworld   \n\n   Goodbye   '
        const result = cleanTerminalLineBreaks(input)
        expect(result).toBe('Hello world\n\nGoodbye')
    })

    it('filters out blank paragraphs that arise from leading/trailing newlines', () => {
        const input = '\n\nHello world\n\n'
        const result = cleanTerminalLineBreaks(input)
        expect(result).toBe('Hello world')
    })
})
