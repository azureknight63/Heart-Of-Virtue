import { useState, useEffect, useRef } from 'react'
import apiEndpoints from '../api/endpoints'
import { useToast } from '../context/ToastContext'
import BaseDialog from './BaseDialog'
import GameButton from './GameButton'
import GameText from './GameText'
import GamePanel from './GamePanel'
import { useHorizontalScrollIndicators } from '../hooks/useScrollIndicators'
import { colors, spacing } from '../styles/theme';
import { displayNameOf } from '../utils/combatMoveStatus';
import { apiErrorMessage } from '../utils/apiError';

/**
 * The equipped weapon's `subtype` (e.g. "Axe", "Sword" — see src/skilltree.py,
 * whose category keys are exactly these subtype strings) if the player has
 * one equipped, else null. Reads `player.inventory` the way ItemCard/PartyPanel
 * do: `maintype`/`subtype`/`is_equipped` off the serialized item, never a
 * `player.equipped` attribute — that one doesn't exist (issue #430).
 */
function equippedWeaponSubtype(player) {
  const weapon = (player?.inventory || []).find(
    (it) => it?.is_equipped && it?.maintype === 'Weapon'
  )
  return weapon?.subtype || null
}

/**
 * SkillsPanel - View and learn character skills categorized by discipline
 */
export default function SkillsPanel({ player, onClose }) {
  const [skillsData, setSkillsData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [selectedCategory, setSelectedCategory] = useState(null)
  const { error: showError } = useToast()
  const tabStripRef = useRef(null)
  const { showLeft: showTabsLeft, showRight: showTabsRight, ref: tabScrollRef } = useHorizontalScrollIndicators()

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
            // Open on the tab matching the equipped weapon type when that
            // discipline has XP to spend; otherwise fall back to the first
            // one with XP, same as before (#540 item 5 — this used to always
            // open on whichever category the tree object happened to list
            // first, e.g. Axe, even with a sword equipped).
            const equippedType = equippedWeaponSubtype(player)
            const defaultCategory = equippedType && categories.includes(equippedType)
              ? equippedType
              : categories[0]
            setSelectedCategory(defaultCategory)
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
      showError(apiErrorMessage(err, 'Failed to learn skill'))
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
        {/* Nothing to select yet. Every other block below is gated on
            `selectedCategory`, which stays null while no discipline has XP —
            including the "No skills currently available" copy — so a fresh
            character was shown a 300px blank box with no explanation (#565).
            The copy teaches the mechanism, which this panel is the only place
            to learn: skill XP is banked per weapon subtype during combat
            (Player.gain_exp in src/player/_leveling.py). */}
        {categories.length === 0 && (
          <GamePanel padding="md" style={{ flex: 1, display: 'flex', flexDirection: 'column', justifyContent: 'center', gap: spacing.sm }}>
            <GameText variant="muted" align="center" style={{ fontStyle: 'italic' }}>
              No skill experience yet.
            </GameText>
            <GameText variant="muted" size="sm" align="center">
              A discipline appears here once you have earned experience in it.
              Fight with a weapon and its discipline — Axe, Sword, and so on —
              opens up with XP to spend on the abilities below it.
            </GameText>
          </GamePanel>
        )}

        {/* Discipline Tabs — chevrons appear only when the strip actually has
            more to scroll to (#540 item 5: it could be cut off mid-word with
            no way to see there was more). */}
        <div style={{ position: 'relative', display: 'flex', alignItems: 'center', gap: spacing.xs }}>
          {showTabsLeft && (
            <GameButton
              onClick={() => tabStripRef.current?.scrollBy({ left: -120, behavior: 'smooth' })}
              variant="secondary"
              size="small"
              aria-label="Scroll disciplines left"
              style={{ flexShrink: 0, padding: '4px 8px' }}
            >
              ‹
            </GameButton>
          )}
          <div
            ref={(node) => { tabStripRef.current = node; tabScrollRef(node) }}
            data-testid="skills-tab-strip"
            style={{
              display: 'flex',
              gap: spacing.xs,
              overflowX: 'auto',
              paddingBottom: spacing.xs,
              borderBottom: `1px solid ${colors.border.light}`,
              flex: 1,
              minWidth: 0,
            }}
          >
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
          {showTabsRight && (
            <GameButton
              onClick={() => tabStripRef.current?.scrollBy({ left: 120, behavior: 'smooth' })}
              variant="secondary"
              size="small"
              aria-label="Scroll disciplines right"
              style={{ flexShrink: 0, padding: '4px 8px' }}
            >
              ›
            </GameButton>
          )}
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
                    {displayNameOf(skill)}
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
                    // "LEARN (50)" never said what the 50 meant (#540 item 5).
                    // It's this discipline's own skill XP, spent on learning —
                    // not skill points or gold. A tooltip rather than a wider
                    // label change, so it doesn't collide with the XP readout
                    // above whenever the two numbers happen to match.
                    title={`Costs ${skill.required_exp} ${selectedCategory} skill XP to learn`}
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
