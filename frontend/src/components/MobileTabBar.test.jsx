import { render, screen, fireEvent } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'
import MobileTabBar from './MobileTabBar'

describe('MobileTabBar', () => {
  it('renders CHARACTER and MAP tabs in exploration mode', () => {
    render(<MobileTabBar activeTab="character" onTabChange={vi.fn()} mode="exploration" />)
    expect(screen.getByText('CHARACTER')).toBeDefined()
    expect(screen.getByText('MAP')).toBeDefined()
  })

  it('renders COMBAT and BATTLEFIELD tabs in combat mode', () => {
    render(<MobileTabBar activeTab="character" onTabChange={vi.fn()} mode="combat" />)
    expect(screen.getByText('COMBAT')).toBeDefined()
    expect(screen.getByText('BATTLEFIELD')).toBeDefined()
  })

  it('calls onTabChange("character") when character tab is clicked', () => {
    const onTabChange = vi.fn()
    render(<MobileTabBar activeTab="map" onTabChange={onTabChange} mode="exploration" />)
    fireEvent.click(screen.getByText('CHARACTER'))
    expect(onTabChange).toHaveBeenCalledWith('character')
  })

  it('calls onTabChange("map") when map tab is clicked', () => {
    const onTabChange = vi.fn()
    render(<MobileTabBar activeTab="character" onTabChange={onTabChange} mode="exploration" />)
    fireEvent.click(screen.getByText('MAP'))
    expect(onTabChange).toHaveBeenCalledWith('map')
  })

  it('renders both emoji icons', () => {
    render(<MobileTabBar activeTab="character" onTabChange={vi.fn()} mode="exploration" />)
    expect(screen.getByText('🧝')).toBeDefined()
    expect(screen.getByText('🗺️')).toBeDefined()
  })
})
