import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import GameButton from './GameButton'
import GameText from './GameText'

// Delay before the "MAIN MENU" button appears (ms)
const BUTTON_REVEAL_DELAY_MS = 3000

/**
 * GameOverScreen - Full-screen overlay shown when the player dies via a narrative event.
 * Displays a GAME OVER message and, after a short delay, a button to return to the main menu.
 *
 * @param {string}   props.message  - Optional death message to display beneath the heading
 */
export default function GameOverScreen({ message }) {
    const navigate = useNavigate()
    const [showButton, setShowButton] = useState(false)
    const [buttonVisible, setButtonVisible] = useState(false)

    // Reveal the button after the delay, then fade it in
    useEffect(() => {
        const revealTimer = setTimeout(() => {
            setShowButton(true)
            // Tiny extra tick so the CSS transition actually fires
            requestAnimationFrame(() => {
                requestAnimationFrame(() => setButtonVisible(true))
            })
        }, BUTTON_REVEAL_DELAY_MS)

        return () => clearTimeout(revealTimer)
    }, [])

    const handleMainMenu = () => {
        navigate('/menu')
    }

    return (
        <div
            style={{
                position: 'fixed',
                inset: 0,
                zIndex: 9999,
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                justifyContent: 'center',
                gap: '32px',
                background: 'radial-gradient(ellipse at center, #1a0000 0%, #000000 70%)',
                animation: 'gameOverFadeIn 1.5s ease-in forwards',
            }}
        >
            <style>{`
                @keyframes gameOverFadeIn {
                    from { opacity: 0; }
                    to   { opacity: 1; }
                }
                @keyframes gameOverPulse {
                    0%,100% { text-shadow: 0 0 20px #cc000088, 0 0 60px #cc000044; }
                    50%     { text-shadow: 0 0 40px #cc0000cc, 0 0 100px #cc000066; }
                }
                .game-over-btn-enter {
                    opacity: 0;
                    transform: translateY(12px);
                    transition: opacity 0.8s ease, transform 0.8s ease;
                }
                .game-over-btn-enter.visible {
                    opacity: 1;
                    transform: translateY(0);
                }
            `}</style>

            {/* GAME OVER heading */}
            <div style={{
                fontFamily: 'monospace',
                fontSize: 'clamp(48px, 8vw, 96px)',
                fontWeight: 'bold',
                letterSpacing: '0.15em',
                textTransform: 'uppercase',
                color: '#cc0000',
                animation: 'gameOverPulse 3s ease-in-out infinite',
            }}>
                GAME OVER
            </div>

            {/* Optional death message */}
            {message && (
                <div style={{
                    maxWidth: '640px',
                    padding: '0 24px',
                    textAlign: 'center',
                }}>
                    <GameText
                        variant="danger"
                        size="md"
                        style={{
                            lineHeight: '1.7',
                            opacity: 0.85,
                            whiteSpace: 'pre-wrap',
                            fontStyle: 'italic',
                        }}
                    >
                        {message}
                    </GameText>
                </div>
            )}

            {/* MAIN MENU button — fades in after the delay */}
            {showButton && (
                <div className={`game-over-btn-enter${buttonVisible ? ' visible' : ''}`}>
                    <GameButton
                        onClick={handleMainMenu}
                        variant="danger"
                        size="large"
                        style={{
                            padding: '14px 48px',
                            fontSize: '18px',
                            letterSpacing: '0.08em',
                            border: '2px solid #cc0000',
                            boxShadow: '0 0 24px #cc000066',
                        }}
                    >
                        MAIN MENU
                    </GameButton>
                </div>
            )}
        </div>
    )
}
