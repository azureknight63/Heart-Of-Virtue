import { useState, useEffect } from 'react'
import apiEndpoints from '../api/endpoints'
import { useToast } from '../context/ToastContext'
import BaseDialog from './BaseDialog'
import GameButton from './GameButton'
import GameText from './GameText'
import GamePanel from './GamePanel'
import { colors, spacing, fonts, shadows } from '../styles/theme'

/**
 * SkillsPanel - View and learn character skills categorized by discipline
 */
export default function SkillsPanel({ player, onClose }) {
  const [skillsData, setSkillsData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [selectedCategory, setSelectedCategory] = useState(null)
  const { error: showError } = useToast()

  useEffect(() => {
    fetchSkills()
  }, [])

  const fetchSkills = async () => {
    try {
      setLoading(true)
      const response = await apiEndpoints.player.getSkills()
      if (response.data.success) {
        setSkillsData(response.data.skills)
        if (!selectedCategory && response.data.skills.skill_tree) {
          const exp = response.data.skills.skill_exp || {}
          const categories = Object.keys(response.data.skills.skill_tree).filter(cat => (exp[cat] || 0) > 0)
          if (categories.length > 0) {
            setSelectedCategory(categories[0])
          }
        }
      }
    } catch (err) {
      setError('Failed to load skills')
      console.error(err)
    } finally {
      setLoading(false)
    }
  }

  const handleLearn = async (skillName, category) => {
    try {
      const response = await apiEndpoints.player.learnSkill(skillName, category)
      if (response.data.success) {
        setSkillsData(response.data.skills)
      }
    } catch (err) {
      console.error('Failed to learn skill:', err)
      showError(err.response?.data?.error || 'Failed to learn skill')
    }
  }

  if (!player) return null

  if (loading) {
    return (
      <BaseDialog title="⚡ SKILLS" onClose={onClose} zIndex={2000}>
        <div style={{ padding: spacing.xxl, textAlign: 'center' }}>
          <GameText variant="muted" style={{ fontStyle: 'italic' }}>
            Accessing ancient scrolls...
          </GameText>
        </div>
      </BaseDialog>
    )
  }

  if (error || !skillsData) {
    return (
      <BaseDialog title="⚡ SKILLS" onClose={onClose} zIndex={2000}>
        <div style={{ padding: spacing.xl, textAlign: 'center' }}>
          <GameText variant="danger">
            ⚠️ {error || 'No skill data available'}
          </GameText>
        </div>
      </BaseDialog>
    )
  }

  const { skill_tree, skill_exp } = skillsData
  const categories = Object.keys(skill_tree || {}).filter(cat => (skill_exp?.[cat] || 0) > 0)

  return (
    <BaseDialog
      title="⚡ ABILITIES & SKILLS"
      onClose={onClose}
      maxWidth="650px"
      padding="16px"
      zIndex={2000}
    >
      <div style={{ display: 'flex', flexDirection: 'column', gap: spacing.md, minHeight: '300px' }}>
        {/* Discipline Tabs */}
        <div style={{
          display: 'flex',
          gap: spacing.xs,
          overflowX: 'auto',
          paddingBottom: spacing.xs,
          borderBottom: `1px solid ${colors.border.light}`,
        }}>
          {categories.map(cat => (
            <GameButton
              key={cat}
              onClick={() => setSelectedCategory(cat)}
              variant={selectedCategory === cat ? 'primary' : 'secondary'}
              size="small"
              style={{
                whiteSpace: 'nowrap',
                minWidth: '70px',
              }}
            >
              {cat}
            </GameButton>
          ))}
        </div>

        {/* XP Header */}
        {selectedCategory && (
          <GamePanel
            padding="sm"
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              backgroundColor: 'rgba(0, 255, 136, 0.05)',
              borderColor: `${colors.success}44`,
            }}
          >
            <GameText variant="muted" size="xs" style={{ textTransform: 'uppercase' }}>Available {selectedCategory} XP</GameText>
            <GameText variant="success" size="lg" weight="bold">
              {skill_exp[selectedCategory] || 0} XP
            </GameText>
          </GamePanel>
        )}

        {/* Skills Grid/List */}
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))',
          gap: spacing.md,
          overflowY: 'auto',
          maxHeight: '45vh',
          padding: spacing.xs,
        }}>
          {selectedCategory && skill_tree[selectedCategory]?.map((skill, idx) => (
            <GamePanel key={idx} padding="md" style={{
              backgroundColor: skill.is_known ? 'rgba(0, 255, 136, 0.05)' : 'rgba(0,0,0,0.2)',
              borderColor: skill.is_known ? `${colors.success}66` : colors.border.light,
              display: 'flex',
              flexDirection: 'column',
              gap: spacing.sm,
              transition: 'all 0.2s',
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                <div style={{ display: 'flex', flexDirection: 'column' }}>
                  <GameText
                    variant={skill.is_known ? 'success' : 'primary'}
                    weight="bold"
                    size="md"
                  >
                    {skill.name}
                  </GameText>
                  {skill.is_known && (
                    <GameText variant="success" size="xs" weight="bold" style={{ textTransform: 'uppercase' }}>
                      ✓ Learned
                    </GameText>
                  )}
                </div>
                {!skill.is_known && (
                  <GameButton
                    onClick={() => handleLearn(skill.name, selectedCategory)}
                    disabled={!skill.can_learn}
                    variant={skill.can_learn ? 'primary' : 'secondary'}
                    size="small"
                  >
                    LEARN ({skill.required_exp})
                  </GameButton>
                )}
              </div>

              <GameText variant="muted" size="sm" style={{ fontStyle: 'italic', flex: 1, lineHeight: '1.4' }}>
                {skill.description}
              </GameText>

              {!skill.is_known && !skill.can_learn && (
                <GameText variant="danger" size="xs">
                  Requires {skill.required_exp} {selectedCategory} XP
                </GameText>
              )}
            </GamePanel>
          ))}

          {selectedCategory && (!skill_tree[selectedCategory] || skill_tree[selectedCategory].length === 0) && (
            <div style={{ gridColumn: '1 / -1', textAlign: 'center', padding: spacing.xxl }}>
              <GameText variant="muted" style={{ fontStyle: 'italic' }}>
                No skills currently available in this discipline.
              </GameText>
            </div>
          )}
        </div>

        <div style={{ display: 'flex', justifyContent: 'center', marginTop: spacing.sm }}>
          <GameButton onClick={onClose} variant="secondary" size="small">
            CLOSE BOOK
          </GameButton>
        </div>
      </div>
    </BaseDialog>
  )
}
