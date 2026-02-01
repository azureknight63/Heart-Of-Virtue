import React, { useState } from 'react';
import { useAudio } from '../context/AudioContext';
import BaseDialog from './BaseDialog';
import GameButton from './GameButton';

/**
 * CombatInputDialog - Versatile dialog for combat-specific inputs (targeting, directions, etc.)
 */
const CombatInputDialog = ({ inputType, options, onSelect, onCancel, onTargetHover }) => {
    const { playSFX } = useAudio();

    const getTitle = () => {
        switch (inputType) {
            case 'target_selection': return '🎯 SELECT TARGET';
            case 'direction_selection': return '🧭 SELECT DIRECTION';
            case 'item_selection': return '🎒 SELECT ITEM';
            case 'number_input': return '🔢 ENTER VALUE';
            default: return '❓ SELECT OPTION';
        }
    };

    const handleSelect = (option) => {
        playSFX('attack');
        // Clear hover when selecting
        if (onTargetHover) onTargetHover(null);
        onSelect(option);
    };

    const renderOptions = () => {
        if (!options || (Array.isArray(options) && options.length === 0)) {
            return (
                <div style={{ color: '#888', fontStyle: 'italic', textAlign: 'center', padding: '40px' }}>
                    No valid targets or options available.
                </div>
            );
        }

        switch (inputType) {
            case 'target_selection':
                return (
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '12px' }}>
                        {Array.isArray(options) && options.map((target, index) => (
                            <div
                                key={index}
                                onMouseEnter={() => onTargetHover && onTargetHover(target.id)}
                                onMouseLeave={() => onTargetHover && onTargetHover(null)}
                                style={{
                                    backgroundColor: 'rgba(255, 255, 255, 0.03)',
                                    border: '1px solid rgba(255, 255, 255, 0.1)',
                                    borderRadius: '12px',
                                    padding: '16px',
                                    display: 'flex',
                                    flexDirection: 'column',
                                    gap: '12px',
                                    transition: 'all 0.2s ease',
                                    cursor: 'pointer'
                                }}
                                onClick={() => handleSelect(target.id)}
                            >
                                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                                    <span style={{ fontWeight: 'bold', color: '#fff', fontSize: '15px' }}>{target.name}</span>
                                    {target.distance !== undefined && (
                                        <span style={{ fontSize: '11px', color: '#aaa', backgroundColor: 'rgba(255,255,255,0.1)', padding: '2px 6px', borderRadius: '4px' }}>
                                            {target.distance} ft
                                        </span>
                                    )}
                                </div>

                                <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                                    {target.health && (
                                        <div style={{ fontSize: '12px', color: '#ff6666', display: 'flex', alignItems: 'center', gap: '6px' }}>
                                            <span style={{ minWidth: '30px', opacity: 0.6 }}>HP:</span>
                                            <div style={{ flex: 1, height: '4px', backgroundColor: 'rgba(255,0,0,0.2)', borderRadius: '2px' }}>
                                                <div style={{ width: `${(target.health.current / target.health.max) * 100}%`, height: '100%', backgroundColor: '#ff6666', borderRadius: '2px' }} />
                                            </div>
                                            <span style={{ fontSize: '10px' }}>{target.health.current}/{target.health.max}</span>
                                        </div>
                                    )}
                                    {target.hit_chance !== undefined && (
                                        <div style={{ fontSize: '12px', color: '#00ffcc', display: 'flex', justifyContent: 'space-between' }}>
                                            <span>Accuracy:</span>
                                            <span style={{ fontWeight: 'bold' }}>{Math.round(target.hit_chance * 100)}%</span>
                                        </div>
                                    )}
                                </div>

                                <GameButton variant="primary" style={{ width: '100%', padding: '8px', pointerEvents: 'none' }}>
                                    STRIKE
                                </GameButton>
                            </div>
                        ))}
                    </div>
                );

            case 'direction_selection':
                return (
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '16px', maxWidth: '300px', margin: '0 auto' }}>
                        {Array.isArray(options) && options.map((direction, index) => (
                            <GameButton
                                key={index}
                                onClick={() => handleSelect(direction)}
                                variant="secondary"
                                style={{ padding: '20px', fontSize: '16px' }}
                            >
                                {direction.toUpperCase()}
                            </GameButton>
                        ))}
                    </div>
                );

            case 'number_input':
                return <NumberInput options={options} onSubmit={handleSelect} />;

            default:
                return (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                        {Array.isArray(options) && options.map((option, index) => (
                            <GameButton
                                key={index}
                                onClick={() => handleSelect(typeof option === 'object' ? option.id : option)}
                                variant="secondary"
                                style={{ textAlign: 'left', justifyContent: 'flex-start', padding: '12px 20px' }}
                            >
                                {typeof option === 'object' ? option.name || option.label : option}
                            </GameButton>
                        ))}
                    </div>
                );
        }
    };

    return (
        <BaseDialog
            title={getTitle()}
            onClose={onCancel}
            maxWidth="600px"
            zIndex={2500}
            variant={inputType === 'target_selection' ? 'no-blur' : undefined}
            containerCentered={true}
        >
            <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
                <div style={{ overflowY: 'auto', maxHeight: '50vh', padding: '4px' }}>
                    {renderOptions()}
                </div>
                {onCancel && (
                    <div style={{ display: 'flex', justifyContent: 'center' }}>
                        <GameButton onClick={onCancel} variant="secondary">
                            CANCEL ACTION
                        </GameButton>
                    </div>
                )}
            </div>
        </BaseDialog>
    );
};

// Internal components for specific input types
const NumberInput = ({ options, onSubmit }) => {
    const [inputValue, setInputValue] = useState(options?.default || options?.min || 5);
    const min = options?.min || 1;
    const max = options?.max || 100;

    return (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '20px', alignItems: 'center' }}>
            {options?.prompt && (
                <div style={{ color: '#aaa', fontSize: '14px', textAlign: 'center', maxWidth: '300px' }}>
                    {options.prompt}
                </div>
            )}
            <div style={{ display: 'flex', alignItems: 'center', gap: '20px' }}>
                <GameButton
                    onClick={() => setInputValue(Math.max(min, inputValue - 1))}
                    variant="secondary"
                    style={{ padding: '10px 20px', fontSize: '24px' }}
                >
                    −
                </GameButton>
                <div style={{
                    fontSize: '32px',
                    fontWeight: 'bold',
                    color: '#ffaa00',
                    fontFamily: 'monospace',
                    minWidth: '80px',
                    textAlign: 'center'
                }}>
                    {inputValue}
                </div>
                <GameButton
                    onClick={() => setInputValue(Math.min(max, inputValue + 1))}
                    variant="secondary"
                    style={{ padding: '10px 20px', fontSize: '24px' }}
                >
                    +
                </GameButton>
            </div>
            <div style={{ fontSize: '11px', color: '#666', textTransform: 'uppercase', letterSpacing: '1px' }}>
                Range: {min} - {max}
            </div>
            <GameButton
                onClick={() => onSubmit(inputValue)}
                variant="primary"
                style={{ width: '200px', padding: '12px' }}
            >
                CONFIRM
            </GameButton>
        </div>
    );
};

export default CombatInputDialog;
