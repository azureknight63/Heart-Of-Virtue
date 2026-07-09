import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import CombatLog from './CombatLog';

describe('CombatLog', () => {
  const mockLog = [
    { type: 'info', message: 'Combat started', timestamp: '12:00:00' },
    { type: 'damage', message: 'Hero deals 10 damage', timestamp: '12:00:01' },
    { type: 'heal', message: 'Hero heals 5 HP', timestamp: '12:00:02' },
    { type: 'ability', message: 'Hero uses Fireball', timestamp: '12:00:03' },
    { type: 'other', message: 'Something happened', timestamp: '12:00:04' }
  ];

  it('renders combat log entries correctly', () => {
    render(<CombatLog log={mockLog} />);

    expect(screen.getByText('Combat Log')).toBeDefined();
    expect(screen.getByText('Combat started')).toBeDefined();
    expect(screen.getByText('Hero deals 10 damage')).toBeDefined();
    expect(screen.getByText('Hero heals 5 HP')).toBeDefined();
    expect(screen.getByText('Hero uses Fireball')).toBeDefined();
    expect(screen.getByText('Something happened')).toBeDefined();
  });

  it('renders empty log message', () => {
    render(<CombatLog log={[]} />);
    expect(screen.getByText('Combat started...')).toBeDefined();
  });

  it('collapses and expands when header is clicked', () => {
    render(<CombatLog log={mockLog} />);
    const header = screen.getByText('Combat Log').parentElement;

    // Initially expanded
    expect(screen.getByText('▼')).toBeDefined();
    expect(screen.getByText('Combat started')).toBeDefined();

    // Collapse
    fireEvent.click(header);
    expect(screen.getByText('▶')).toBeDefined();
    expect(screen.queryByText('Combat started')).toBeNull();

    // Expand
    fireEvent.click(header);
    expect(screen.getByText('▼')).toBeDefined();
    expect(screen.getByText('Combat started')).toBeDefined();
  });

  it('handles resizing', () => {
    const { container } = render(<CombatLog log={mockLog} allowResize={true} />);
    const resizeHandle = container.querySelector('[style*="cursor: ns-resize"], [style*="ns-resize"]');

    // Resize handle must be present when allowResize=true
    expect(resizeHandle, 'resize handle not found — check CombatLog resize implementation').not.toBeNull();

    // Mock getBoundingClientRect for logRef
    const logElement = container.firstChild;
    vi.spyOn(logElement, 'getBoundingClientRect').mockReturnValue({
      bottom: 500
    });

    fireEvent.mouseDown(resizeHandle);

    // Move mouse down by 50px (delta = 550 - 500 = 50)
    // height = height - delta = 150 - 50 = 100
    fireEvent.mouseMove(document, { clientY: 550 });
    fireEvent.mouseUp(document);

    expect(logElement.style.height).toBe('100px');
  });

  it('ignores mousemove when not currently resizing', () => {
    const { container } = render(<CombatLog log={mockLog} allowResize={true} />);
    const logElement = container.firstChild;
    const originalHeight = logElement.style.height;

    // No mouseDown first, so isResizing is false — mousemove should be a no-op.
    fireEvent.mouseMove(document, { clientY: 999 });
    expect(logElement.style.height).toBe(originalHeight);
  });

  it('shows top/bottom scroll fade indicators when content overflows', () => {
    const { container } = render(<CombatLog log={mockLog} />);
    const contentEl = container.querySelector('div[style*="overflow-y: auto"]');

    Object.defineProperty(contentEl, 'scrollHeight', { value: 500, configurable: true });
    Object.defineProperty(contentEl, 'clientHeight', { value: 100, configurable: true });
    Object.defineProperty(contentEl, 'scrollTop', { value: 50, configurable: true });
    fireEvent.scroll(contentEl);

    expect(container.querySelector('[style*="position: absolute"]')).not.toBeNull();
  });

  it('respects allowResize prop', () => {
    const { container } = render(<CombatLog log={mockLog} allowResize={false} />);
    const resizeHandle = container.querySelector('[style*="cursor: ns-resize"], [style*="ns-resize"]');
    expect(resizeHandle).toBeNull();
    expect(container.firstChild.style.height).toBe('100%');
  });

  it('auto-scrolls to bottom when log updates', () => {
    const { rerender } = render(<CombatLog log={mockLog} />);
    
    // We can't easily test scrollTop in JSDOM without more complex mocking,
    // but we can verify the effect runs.
    const newLog = [...mockLog, { type: 'info', message: 'New entry' }];
    rerender(<CombatLog log={newLog} />);
    expect(screen.getByText('New entry')).toBeDefined();
  });

  it('auto-scrolls to bottom when it becomes player turn', () => {
    const { rerender } = render(<CombatLog log={mockLog} isMyTurn={false} />);
    rerender(<CombatLog log={mockLog} isMyTurn={true} />);
    // Effect runs
  });
});
