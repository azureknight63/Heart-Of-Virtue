import { render } from '@testing-library/react'
import { describe, it, expect } from 'vitest'
import ScrollFadeIndicator from './ScrollFadeIndicator'

describe('ScrollFadeIndicator', () => {
  it('defaults to a bottom-positioned indicator', () => {
    const { container } = render(<ScrollFadeIndicator />)
    const div = container.querySelector('div')
    expect(div.style.bottom).toBe('0px')
    expect(div.style.top).toBe('')
    expect(container.textContent).toContain('▼')
    expect(container.textContent).toContain('scroll')
  })

  it('renders a top-positioned indicator when position="top"', () => {
    const { container } = render(<ScrollFadeIndicator position="top" />)
    const div = container.querySelector('div')
    expect(div.style.top).toBe('0px')
    expect(div.style.bottom).toBe('')
    expect(container.textContent).toContain('▲')
  })

  it('applies a custom color to the label', () => {
    const { container } = render(<ScrollFadeIndicator color="#ff0000" />)
    const label = container.querySelector('.scroll-indicator-label')
    expect(label.style.color).toBe('rgb(255, 0, 0)')
  })

  it('applies a custom background color to the gradient', () => {
    const { container } = render(<ScrollFadeIndicator bgColor="#123456" />)
    const div = container.querySelector('div')
    expect(div.style.background).toContain('rgb(18, 52, 86)')
  })
})
