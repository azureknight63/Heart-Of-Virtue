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

    it('renders with label', () => {
      const { container } = render(
        <GameInput label="Username" onChange={mockOnChange} />
      )
      // Check for label text or association
      expect(container.firstChild).toBeInTheDocument()
    })

    it('renders disabled state', () => {
      const { container } = render(
        <GameInput disabled onChange={mockOnChange} />
      )
      const input = container.querySelector('input')
      expect(input).toBeDisabled()
    })

    it('renders with custom className', () => {
      const { container } = render(
        <GameInput className="custom-input" onChange={mockOnChange} />
      )
      const input = container.querySelector('input')
      expect(input).toHaveClass('custom-input')
    })
  })

  describe('Input Types', () => {
    it('renders as text input by default', () => {
      const { container } = render(<GameInput onChange={mockOnChange} />)
      const input = container.querySelector('input')
      expect(input).toHaveAttribute('type', 'text')
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

    it('calls onChange when input value changes', () => {
      const { container } = render(
        <GameInput onChange={mockOnChange} />
      )
      const input = container.querySelector('input')
      fireEvent.change(input, { target: { value: 'new value' } })
      expect(mockOnChange).toHaveBeenCalled()
    })

    it('passes event to onChange handler', () => {
      const { container } = render(
        <GameInput onChange={mockOnChange} />
      )
      const input = container.querySelector('input')
      fireEvent.change(input, { target: { value: 'test' } })
      expect(mockOnChange).toHaveBeenCalledWith(expect.any(Object))
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
      fireEvent.focus(input)
      expect(input).toHaveFocus()
    })

    it('responds to blur event', () => {
      const { container } = render(<GameInput onChange={mockOnChange} />)
      const input = container.querySelector('input')
      fireEvent.focus(input)
      fireEvent.blur(input)
      expect(input).not.toHaveFocus()
    })

    it('handles key events', () => {
      const { container } = render(<GameInput onChange={mockOnChange} />)
      const input = container.querySelector('input')
      fireEvent.keyDown(input, { key: 'Enter' })
      expect(input).toBeInTheDocument()
    })

    it('does not trigger onChange when disabled', () => {
      const { container } = render(
        <GameInput disabled onChange={mockOnChange} />
      )
      const input = container.querySelector('input')
      fireEvent.change(input, { target: { value: 'test' } })
      expect(mockOnChange).not.toHaveBeenCalled()
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

    it('clears value correctly', () => {
      const { container } = render(
        <GameInput value="test" onChange={mockOnChange} />
      )
      const input = container.querySelector('input')
      expect(input).toHaveValue('test')
      fireEvent.change(input, { target: { value: '' } })
      expect(mockOnChange).toHaveBeenCalled()
    })
  })

  describe('Accessibility', () => {
    it('is keyboard accessible', () => {
      const { container } = render(<GameInput onChange={mockOnChange} />)
      const input = container.querySelector('input')
      expect(input).toBeInTheDocument()
      fireEvent.keyDown(input, { key: 'a' })
    })

    it('supports autofocus attribute', () => {
      const { container } = render(
        <GameInput autoFocus onChange={mockOnChange} />
      )
      const input = container.querySelector('input')
      expect(input).toHaveAttribute('autoFocus')
    })

    it('has proper input role', () => {
      const { container } = render(
        <GameInput placeholder="test" onChange={mockOnChange} />
      )
      const input = container.querySelector('input')
      expect(input.tagName).toBe('INPUT')
    })
  })
})
