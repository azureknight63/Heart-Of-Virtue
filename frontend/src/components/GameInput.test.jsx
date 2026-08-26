import React from 'react'
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import GameInput from './GameInput'

describe('GameInput', () => {
  const mockOnChange = vi.fn()

  beforeEach(() => {
    vi.clearAllMocks()
  })

  describe('Rendering', () => {
    it('renders input element', () => {
      const { container } = render(<GameInput onChange={mockOnChange} />)
      const input = container.querySelector('input')
      expect(input).toBeInTheDocument()
    })

    it('renders with placeholder text', () => {
      render(<GameInput placeholder="Enter text" onChange={mockOnChange} />)
      const input = screen.getByPlaceholderText('Enter text')
      expect(input).toBeInTheDocument()
    })

    it('renders the label text above the input, and none when there is no label', () => {
      // Was: `expect(container.firstChild).toBeInTheDocument()` — the wrapper
      // div, which renders for every GameInput whether or not a label is given.
      const { container, rerender } = render(
        <GameInput label="Username" onChange={mockOnChange} />
      )
      const label = container.querySelector('label')
      expect(label.textContent).toBe('Username')
      // Label first, then the field.
      expect(container.firstChild.firstChild).toBe(label)

      rerender(<GameInput onChange={mockOnChange} />)
      expect(container.querySelector('label')).toBeNull()
    })

    it('renders disabled state', () => {
      const { container } = render(
        <GameInput disabled onChange={mockOnChange} />
      )
      const input = container.querySelector('input')
      expect(input).toBeDisabled()
    })

    it('renders the error message and error styling when error is provided', () => {
      const { container } = render(
        <GameInput label="Username" error="This field is required" onChange={mockOnChange} />
      )
      expect(screen.getByText('This field is required')).toBeInTheDocument()
      const input = container.querySelector('input')
      expect(input.style.borderColor).not.toBe('')
    })

    it('does not render an error message when error is absent', () => {
      render(<GameInput onChange={mockOnChange} />)
      expect(screen.queryByText(/required/i)).not.toBeInTheDocument()
    })

    it('renders with custom className', () => {
      const { container } = render(
        <GameInput className="custom-input" onChange={mockOnChange} />
      )
      const inputContainer = container.querySelector('.game-input-container')
      expect(inputContainer).toHaveClass('custom-input')
    })
  })

  describe('Input Types', () => {
    it('renders as text input by default', () => {
      const { container } = render(<GameInput onChange={mockOnChange} />)
      const input = container.querySelector('input')
      // Input defaults to text type, but React may not set the attribute if not provided
      expect(input?.type).toBe('text')
    })

    it('renders as password input when type is password', () => {
      const { container } = render(
        <GameInput type="password" onChange={mockOnChange} />
      )
      const input = container.querySelector('input')
      expect(input).toHaveAttribute('type', 'password')
    })

    it('renders as number input when type is number', () => {
      const { container } = render(
        <GameInput type="number" onChange={mockOnChange} />
      )
      const input = container.querySelector('input')
      expect(input).toHaveAttribute('type', 'number')
    })

    it('renders as email input when type is email', () => {
      const { container } = render(
        <GameInput type="email" onChange={mockOnChange} />
      )
      const input = container.querySelector('input')
      expect(input).toHaveAttribute('type', 'email')
    })
  })

  describe('Value Handling', () => {
    it('renders with initial value', () => {
      const { container } = render(
        <GameInput value="initial" onChange={mockOnChange} />
      )
      const input = container.querySelector('input')
      expect(input).toHaveValue('initial')
    })

    it('forwards the raw change event, with the typed value on event.target', () => {
      // Merged from two tests: one asserted only `toHaveBeenCalled()`, the
      // other `toHaveBeenCalledWith(expect.any(Object))` — which any argument
      // at all satisfies. Every caller in the app reads `e.target.value`, so
      // that is the contract worth pinning.
      const { container } = render(<GameInput onChange={mockOnChange} />)
      const input = container.querySelector('input')

      fireEvent.change(input, { target: { value: 'new value' } })

      expect(mockOnChange).toHaveBeenCalledTimes(1)
      const event = mockOnChange.mock.calls[0][0]
      expect(event.target).toBe(input)
      expect(event.target.value).toBe('new value')
    })

    it('handles empty value', () => {
      const { container } = render(
        <GameInput value="" onChange={mockOnChange} />
      )
      const input = container.querySelector('input')
      expect(input).toHaveValue('')
    })
  })

  describe('Interactions', () => {
    it('responds to focus event', () => {
      const { container } = render(<GameInput onChange={mockOnChange} />)
      const input = container.querySelector('input')
      input.focus()
      expect(document.activeElement).toBe(input)
    })

    it('responds to blur event', () => {
      const { container } = render(<GameInput onChange={mockOnChange} />)
      const input = container.querySelector('input')
      fireEvent.focus(input)
      fireEvent.blur(input)
      expect(input).not.toHaveFocus()
    })

    it('forwards keyboard handlers through to the DOM input', () => {
      // Was: fire a keyDown, then assert the input still exists. GameInput
      // spreads `...props` onto <input>, so the checkable claim is that an
      // arbitrary handler actually arrives there.
      const onKeyDown = vi.fn()
      const { container } = render(<GameInput onChange={mockOnChange} onKeyDown={onKeyDown} />)
      const input = container.querySelector('input')

      fireEvent.keyDown(input, { key: 'Enter' })
      expect(onKeyDown).toHaveBeenCalledTimes(1)
      expect(onKeyDown.mock.calls[0][0].key).toBe('Enter')
      expect(mockOnChange).not.toHaveBeenCalled()
    })

    it('renders with disabled attribute', () => {
      const { container } = render(
        <GameInput disabled onChange={mockOnChange} />
      )
      const input = container.querySelector('input')
      expect(input).toHaveAttribute('disabled')
    })
  })

  describe('Attributes', () => {
    it('renders with custom name attribute', () => {
      const { container } = render(
        <GameInput name="username" onChange={mockOnChange} />
      )
      const input = container.querySelector('input')
      expect(input).toHaveAttribute('name', 'username')
    })

    it('renders with id attribute', () => {
      const { container } = render(
        <GameInput id="input-1" onChange={mockOnChange} />
      )
      const input = container.querySelector('input')
      expect(input).toHaveAttribute('id', 'input-1')
    })

    it('renders with required attribute', () => {
      const { container } = render(
        <GameInput required onChange={mockOnChange} />
      )
      const input = container.querySelector('input')
      expect(input).toHaveAttribute('required')
    })

    it('renders with maxLength attribute', () => {
      const { container } = render(
        <GameInput maxLength="50" onChange={mockOnChange} />
      )
      const input = container.querySelector('input')
      expect(input).toHaveAttribute('maxLength', '50')
    })

    it('renders with pattern attribute', () => {
      const { container } = render(
        <GameInput pattern="[0-9]+" onChange={mockOnChange} />
      )
      const input = container.querySelector('input')
      expect(input).toHaveAttribute('pattern', '[0-9]+')
    })
  })

  describe('Styling', () => {
    it('applies custom style prop', () => {
      const { container } = render(
        <GameInput style={{ padding: '10px' }} onChange={mockOnChange} />
      )
      const input = container.querySelector('input')
      expect(input).toHaveStyle({ padding: '10px' })
    })

    it('applies monospace font family', () => {
      const { container } = render(<GameInput onChange={mockOnChange} />)
      const input = container.querySelector('input')
      const styles = window.getComputedStyle(input)
      expect(styles.fontFamily).toContain('monospace')
    })
  })

  describe('Edge Cases', () => {
    it('handles very long input values', () => {
      const longValue = 'a'.repeat(1000)
      const { container } = render(
        <GameInput value={longValue} onChange={mockOnChange} />
      )
      const input = container.querySelector('input')
      expect(input).toHaveValue(longValue)
    })

    it('handles special characters in value', () => {
      const { container } = render(
        <GameInput value="!@#$%^&*()" onChange={mockOnChange} />
      )
      const input = container.querySelector('input')
      expect(input).toHaveValue('!@#$%^&*()')
    })

    it('handles rapid onChange calls', () => {
      const { container } = render(
        <GameInput onChange={mockOnChange} />
      )
      const input = container.querySelector('input')
      fireEvent.change(input, { target: { value: 'a' } })
      fireEvent.change(input, { target: { value: 'ab' } })
      fireEvent.change(input, { target: { value: 'abc' } })
      expect(mockOnChange).toHaveBeenCalledTimes(3)
    })

    it('reports a cleared field as an empty string, not undefined', () => {
      // The value must be read INSIDE the handler: React restores
      // input.value to match the `value` prop before the assertion runs, so a
      // spy's recorded event shows the old text.
      const seen = []
      const { container } = render(
        <GameInput value="test" onChange={(e) => seen.push(e.target.value)} />
      )
      const input = container.querySelector('input')
      expect(input).toHaveValue('test')

      fireEvent.change(input, { target: { value: '' } })
      expect(seen).toEqual([''])
      // Controlled: the DOM does not clear until the parent lowers `value`.
      expect(input).toHaveValue('test')
    })
  })

  describe('Accessibility', () => {
    it.each([
      ['an enabled input takes focus', {}, true],
      ['a disabled input refuses it', { disabled: true }, false],
    ])('%s', (_label, props, shouldFocus) => {
      // Was "is keyboard accessible", which asserted the input existed and then
      // fired a keyDown with no assertion after it.
      const { container } = render(<GameInput onChange={mockOnChange} {...props} />)
      const input = container.querySelector('input')
      input.focus()
      expect(document.activeElement === input).toBe(shouldFocus)
    })

    it('takes focus on mount with autoFocus', () => {
      // Was "accepts autofocus as a prop", asserting only that the input
      // existed — true with or without the prop.
      const { container } = render(<GameInput autoFocus onChange={mockOnChange} />)
      expect(container.querySelector('input')).toHaveFocus()
    })

    it('associates a label with its input through htmlFor/id', () => {
      // The label is only useful if it is wired to the field; GameInput renders
      // `htmlFor={id}`, so an id-less GameInput with a label is a broken label.
      render(<GameInput id="jean-name" label="Name" onChange={mockOnChange} />)
      const input = screen.getByLabelText('Name')
      expect(input.tagName).toBe('INPUT')
      expect(input.id).toBe('jean-name')
    })
  })
})
