import { colors, spacing, fonts } from '../styles/theme'
import GameText from './GameText'

export default function LoadingScreen() {
  return (
    <div style={{
      width: '100vw',
      height: '100vh',
      backgroundColor: colors.bg.main,
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center'
    }}>
      <div style={{ textAlign: 'center' }}>
        <GameText variant="primary" weight="bold" style={{ fontSize: '3rem', marginBottom: spacing.xl, animation: 'pulse-glow 2s infinite' }}>
          Heart of Virtue
        </GameText>
        <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', gap: spacing.sm, marginBottom: spacing.xl }}>
          <div style={{ width: '12px', height: '12px', backgroundColor: colors.secondary, borderRadius: '50%', animation: 'bounce 1s infinite', animationDelay: '0s' }}></div>
          <div style={{ width: '12px', height: '12px', backgroundColor: colors.secondary, borderRadius: '50%', animation: 'bounce 1s infinite', animationDelay: '0.2s' }}></div>
          <div style={{ width: '12px', height: '12px', backgroundColor: colors.secondary, borderRadius: '50%', animation: 'bounce 1s infinite', animationDelay: '0.4s' }}></div>
        </div>
        <GameText variant="info" size="sm">Initializing game world...</GameText>
      </div>
    </div>
  )
}
