import React from 'react';
import { colors } from '../styles/theme';

export default function TacticalAnalysisPanel({ combat }) {
    if (!combat || !combat.enemies) return null;

    const player = combat.player;

    return (
        <div style={{
            position: 'absolute',
            left: '20px',
            bottom: '20px',
            width: '260px',
            backgroundColor: 'rgba(10, 15, 25, 0.85)',
            border: `1px solid ${colors.secondary}88`,
            borderRadius: '6px',
            padding: '12px',
            fontFamily: 'monospace',
            color: colors.text.highlight,
            zIndex: 100,
            boxShadow: `0 0 15px ${colors.secondary}22`,
            pointerEvents: 'none'
        }}>
            <div style={{
                fontSize: '11px',
                fontWeight: 'bold',
                color: colors.secondary,
                marginBottom: '8px',
                borderBottom: `1px solid ${colors.secondary}44`,
                paddingBottom: '4px',
                display: 'flex',
                justifyContent: 'space-between'
            }}>
                <span>TACTICAL MONITOR</span>
                <span>BEAT: {combat.beat || 0}</span>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                {combat.enemies.map((enemy, idx) => {
                    const dist = enemy.distance || 0;
                    const isClosing = false; // Mock for now

                    return (
                        <div key={idx} style={{
                            fontSize: '10px',
                            display: 'flex',
                            justifyContent: 'space-between',
                            alignItems: 'center',
                            backgroundColor: 'rgba(255, 255, 255, 0.03)',
                            padding: '4px 6px',
                            borderRadius: '3px'
                        }}>
                            <span style={{ color: colors.danger }}>{enemy.name.toUpperCase()}</span>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                                <span style={{ color: dist <= 5 ? colors.danger : colors.text.muted }}>
                                    {dist}m
                                </span>
                                {dist <= 5 && <span style={{ color: colors.danger, fontSize: '8px', animation: 'blink 1s infinite' }}>⚠️</span>}
                            </div>
                        </div>
                    );
                })}
            </div>

            {player?.current_move && (
                <div style={{ marginTop: '10px', fontSize: '9px', borderTop: '1px solid rgba(255,255,255,0.1)', paddingTop: '6px' }}>
                    <div style={{ color: colors.text.muted, marginBottom: '2px' }}>CURRENT ACTION:</div>
                    <div style={{ color: colors.primary }}>{player.current_move.name.toUpperCase()}</div>
                    <div style={{ display: 'flex', gap: '4px', marginTop: '4px' }}>
                        {[...Array(player.current_move.total_beats || 0)].map((_, i) => (
                            <div key={i} style={{
                                flex: 1,
                                height: '3px',
                                backgroundColor: i < (player.current_move.total_beats - player.current_move.beats_left) ? colors.primary : '#333',
                                borderRadius: '1px'
                            }} />
                        ))}
                    </div>
                </div>
            )}
        </div>
    );
}
