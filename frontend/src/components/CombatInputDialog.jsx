import React from 'react';
import { useAudio } from '../context/AudioContext';

/**
 * Extensible dialog for handling various combat input requests from the backend.
 * Supports:
 * - target_selection: Select an enemy or ally target
 * - direction_selection: Select a direction (north, south, east, west)
 * - item_selection: Select an item from inventory
 * - number_input: Enter a numeric value
 */
const CombatInputDialog = ({ inputType, options, onSelect, onCancel }) => {
    const { playSFX } = useAudio();

    const getTitle = () => {
        switch (inputType) {
            case 'target_selection':
                return 'SELECT TARGET';
            case 'direction_selection':
                return 'SELECT DIRECTION';
            case 'item_selection':
                return 'SELECT ITEM';
            case 'number_input':
                return 'ENTER VALUE';
            default:
                return 'SELECT OPTION';
        }
    };

    const handleSelect = (option) => {
        playSFX('attack');
        onSelect(option);
    };

    const renderOptions = () => {
        if (!options || options.length === 0) {
            return (
                <div style={{ color: '#888', fontStyle: 'italic', textAlign: 'center', padding: '20px' }}>
                    No options available
                </div>
            );
        }

        switch (inputType) {
            case 'target_selection':
                return options.map((target, index) => (
                    <button
                        key={index}
                        onClick={() => handleSelect(target.id)}
                        style={{
                            backgroundColor: 'rgba(255, 255, 255, 0.05)',
                            border: '1px solid #444',
                            borderRadius: '4px',
                            padding: '12px',
                            textAlign: 'left',
                            cursor: 'pointer',
                            transition: 'all 0.2s ease',
                            display: 'flex',
                            flexDirection: 'column',
                            gap: '6px',
                        }}
                        onMouseEnter={(e) => {
                            e.currentTarget.style.backgroundColor = 'rgba(255, 170, 0, 0.1)';
                            e.currentTarget.style.borderColor = '#ffaa00';
                        }}
                        onMouseLeave={(e) => {
                            e.currentTarget.style.backgroundColor = 'rgba(255, 255, 255, 0.05)';
                            e.currentTarget.style.borderColor = '#444';
                        }}
                    >
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                            <span style={{ fontWeight: 'bold', color: '#eee', fontSize: '14px' }}>{target.name}</span>
                            {target.distance !== undefined && (
                                <span style={{ fontSize: '11px', color: '#aaa' }}>
                                    {target.distance} ft
                                </span>
                            )}
                        </div>
                        {target.health && (
                            <div style={{ fontSize: '11px', color: '#888' }}>
                                HP: {target.health.current}/{target.health.max}
                            </div>
                        )}
                        {target.hit_chance !== undefined && (
                            <div style={{ fontSize: '11px', color: '#88ff88' }}>
                                Hit Chance: {Math.round(target.hit_chance * 100)}%
                            </div>
                        )}
                    </button>
                ));

            case 'direction_selection':
                return options.map((direction, index) => (
                    <button
                        key={index}
                        onClick={() => handleSelect(direction)}
                        style={{
                            backgroundColor: 'rgba(255, 255, 255, 0.05)',
                            border: '1px solid #444',
                            borderRadius: '4px',
                            padding: '12px',
                            textAlign: 'center',
                            cursor: 'pointer',
                            transition: 'all 0.2s ease',
                            fontSize: '14px',
                            fontWeight: 'bold',
                            color: '#eee',
                            textTransform: 'uppercase',
                        }}
                        onMouseEnter={(e) => {
                            e.currentTarget.style.backgroundColor = 'rgba(255, 170, 0, 0.1)';
                            e.currentTarget.style.borderColor = '#ffaa00';
                        }}
                        onMouseLeave={(e) => {
                            e.currentTarget.style.backgroundColor = 'rgba(255, 255, 255, 0.05)';
                            e.currentTarget.style.borderColor = '#444';
                        }}
                    >
                        {direction}
                    </button>
                ));

            case 'number_input':
                const [inputValue, setInputValue] = React.useState(options?.default || 5);
                const min = options?.min || 1;
                const max = options?.max || 100;

                return (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                        {options?.prompt && (
                            <div style={{ color: '#eee', fontSize: '14px', textAlign: 'center' }}>
                                {options.prompt}
                            </div>
                        )}
                        <div style={{ display: 'flex', alignItems: 'center', gap: '12px', justifyContent: 'center' }}>
                            <button
                                onClick={() => setInputValue(Math.max(min, inputValue - 1))}
                                style={{
                                    backgroundColor: 'rgba(255, 255, 255, 0.05)',
                                    border: '1px solid #444',
                                    borderRadius: '4px',
                                    padding: '8px 16px',
                                    cursor: 'pointer',
                                    color: '#eee',
                                    fontSize: '18px',
                                    fontWeight: 'bold',
                                }}
                            >
                                −
                            </button>
                            <input
                                type="number"
                                value={inputValue}
                                onChange={(e) => {
                                    const val = parseInt(e.target.value) || min;
                                    setInputValue(Math.min(max, Math.max(min, val)));
                                }}
                                min={min}
                                max={max}
                                style={{
                                    backgroundColor: 'rgba(255, 255, 255, 0.1)',
                                    border: '1px solid #ffaa00',
                                    borderRadius: '4px',
                                    padding: '12px',
                                    width: '80px',
                                    textAlign: 'center',
                                    color: '#eee',
                                    fontSize: '18px',
                                    fontWeight: 'bold',
                                    fontFamily: 'monospace',
                                    MozAppearance: 'textfield',
                                    WebkitAppearance: 'none',
                                    appearance: 'textfield',
                                }}
                            />
                            <button
                                onClick={() => setInputValue(Math.min(max, inputValue + 1))}
                                style={{
                                    backgroundColor: 'rgba(255, 255, 255, 0.05)',
                                    border: '1px solid #444',
                                    borderRadius: '4px',
                                    padding: '8px 16px',
                                    cursor: 'pointer',
                                    color: '#eee',
                                    fontSize: '18px',
                                    fontWeight: 'bold',
                                }}
                            >
                                +
                            </button>
                        </div>
                        <div style={{ fontSize: '12px', color: '#888', textAlign: 'center' }}>
                            Range: {min} - {max}
                        </div>
                        <button
                            onClick={() => handleSelect(inputValue)}
                            style={{
                                backgroundColor: 'rgba(255, 170, 0, 0.2)',
                                border: '2px solid #ffaa00',
                                borderRadius: '4px',
                                padding: '12px 24px',
                                cursor: 'pointer',
                                color: '#ffaa00',
                                fontSize: '14px',
                                fontWeight: 'bold',
                                textTransform: 'uppercase',
                                transition: 'all 0.2s ease',
                            }}
                            onMouseEnter={(e) => {
                                e.currentTarget.style.backgroundColor = 'rgba(255, 170, 0, 0.3)';
                            }}
                            onMouseLeave={(e) => {
                                e.currentTarget.style.backgroundColor = 'rgba(255, 170, 0, 0.2)';
                            }}
                        >
                            Confirm
                        </button>
                    </div>
                );

            default:
                // Generic option rendering
                return options.map((option, index) => (
                    <button
                        key={index}
                        onClick={() => handleSelect(typeof option === 'object' ? option.id : option)}
                        style={{
                            backgroundColor: 'rgba(255, 255, 255, 0.05)',
                            border: '1px solid #444',
                            borderRadius: '4px',
                            padding: '12px',
                            textAlign: 'left',
                            cursor: 'pointer',
                            transition: 'all 0.2s ease',
                            color: '#eee',
                        }}
                        onMouseEnter={(e) => {
                            e.currentTarget.style.backgroundColor = 'rgba(255, 170, 0, 0.1)';
                            e.currentTarget.style.borderColor = '#ffaa00';
                        }}
                        onMouseLeave={(e) => {
                            e.currentTarget.style.backgroundColor = 'rgba(255, 255, 255, 0.05)';
                            e.currentTarget.style.borderColor = '#444';
                        }}
                    >
                        {typeof option === 'object' ? option.name || option.label : option}
                    </button>
                ));
        }
    };

    return (
        <div style={{
            position: 'fixed',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            backgroundColor: 'rgba(0, 0, 0, 0.8)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 1000,
        }}>
            <div style={{
                backgroundColor: 'rgba(0, 0, 0, 0.95)',
                border: '2px solid #ffaa00',
                borderRadius: '8px',
                padding: '20px',
                minWidth: '320px',
                maxWidth: '500px',
                maxHeight: '70vh',
                display: 'flex',
                flexDirection: 'column',
                color: '#fff',
                fontFamily: 'monospace',
                boxShadow: '0 0 30px rgba(255, 170, 0, 0.5)',
            }}>
                {/* Header */}
                <div style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    marginBottom: '16px',
                    borderBottom: '1px solid #444',
                    paddingBottom: '12px',
                }}>
                    <h3 style={{ margin: 0, color: '#ffaa00', fontSize: '16px', textTransform: 'uppercase' }}>
                        {getTitle()}
                    </h3>
                    {onCancel && (
                        <button
                            onClick={onCancel}
                            style={{
                                background: 'none',
                                border: 'none',
                                color: '#888',
                                cursor: 'pointer',
                                fontSize: '18px',
                                padding: '0 4px',
                            }}
                            title="Cancel"
                        >
                            ✕
                        </button>
                    )}
                </div>

                {/* Options */}
                <div style={{
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '10px',
                    overflowY: 'auto',
                    maxHeight: 'calc(70vh - 100px)',
                }}>
                    {renderOptions()}
                </div>
            </div>
        </div>
    );
};

export default CombatInputDialog;
