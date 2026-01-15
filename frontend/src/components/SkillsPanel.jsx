import { useState, useEffect } from 'react'
import apiEndpoints from '../api/endpoints'
import BaseDialog from './BaseDialog'
import GameButton from './GameButton'

/**
 * SkillsPanel - View and learn character skills categorized by discipline
 */
export default function SkillsPanel({ player, onClose }) {
  const [skillsData, setSkillsData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [selectedCategory, setSelectedCategory] = useState(null)

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
          const categories = Object.keys(response.data.skills.skill_tree)
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
      alert(err.response?.data?.error || 'Failed to learn skill')
    }
  }

  if (!player) return null

  if (loading) {
    return (
      <BaseDialog title="⚡ SKILLS" onClose={onClose} zIndex={2000}>
        <div style={{ padding: '40px', textAlign: 'center', color: '#888', fontStyle: 'italic' }}>
          Accessing ancient scrolls...
        </div>
      </BaseDialog>
    )
  }

  if (error || !skillsData) {
    return (
      <BaseDialog title="⚡ SKILLS" onClose={onClose} zIndex={2000}>
        <div style={{ padding: '20px', color: '#ff4444', textAlign: 'center' }}>
          ⚠️ {error || 'No skill data available'}
        </div>
      </BaseDialog>
    )
  }

  const { skill_tree, skill_exp } = skillsData
  const categories = Object.keys(skill_tree || {})

  return (
    <BaseDialog
      title="⚡ ABILITIES & SKILLS"
      onClose={onClose}
      maxWidth="650px"
      zIndex={2000}
    >
      <div style={{ display: 'flex', flexDirection: 'column', gap: '20px', minHeight: '400px' }}>
        {/* Discipline Tabs */}
        <div style={{
          display: 'flex',
          gap: '8px',
          overflowX: 'auto',
          paddingBottom: '8px',
          borderBottom: '1px solid rgba(255, 255, 0, 0.1)',
        }}>
          {categories.map(cat => (
            <GameButton
              key={cat}
              onClick={() => setSelectedCategory(cat)}
              variant={selectedCategory === cat ? 'primary' : 'secondary'}
              style={{
                padding: '6px 12px',
                fontSize: '12px',
                whiteSpace: 'nowrap',
                minWidth: '80px',
              }}
            >
              {cat}
            </GameButton>
          ))}
        </div>

        {/* XP Header */}
        {selectedCategory && (
          <div style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            backgroundColor: 'rgba(0, 255, 0, 0.05)',
            padding: '10px 16px',
            borderRadius: '8px',
            border: '1px solid rgba(0, 255, 0, 0.1)',
          }}>
            <div style={{ color: '#aaa', fontSize: '11px', textTransform: 'uppercase' }}>Available {selectedCategory} Experience</div>
            <div style={{ color: '#00ff88', fontSize: '18px', fontWeight: 'bold', fontFamily: 'monospace' }}>
              {skill_exp[selectedCategory] || 0} XP
            </div>
          </div>
        )}

        {/* Skills Grid/List */}
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))',
          gap: '12px',
          overflowY: 'auto',
          maxHeight: '45vh',
          padding: '4px',
        }}>
          {selectedCategory && skill_tree[selectedCategory]?.map((skill, idx) => (
            <div key={idx} style={{
              backgroundColor: skill.is_known ? 'rgba(0, 255, 136, 0.05)' : 'rgba(0,0,0,0.2)',
              border: `1px solid ${skill.is_known ? 'rgba(0, 255, 136, 0.3)' : 'rgba(255, 255, 255, 0.1)'}`,
              borderRadius: '10px',
              padding: '16px',
              display: 'flex',
              flexDirection: 'column',
              gap: '10px',
              transition: 'all 0.2s',
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                <div style={{ display: 'flex', flexDirection: 'column' }}>
                  <span style={{
                    color: skill.is_known ? '#00ff88' : '#ffeeaa',
                    fontWeight: 'bold',
                    fontSize: '14px',
                    fontFamily: 'monospace'
                  }}>
                    {skill.name}
                  </span>
                  {skill.is_known && (
                    <span style={{ color: '#00ff88', fontSize: '10px', fontWeight: 'bold', textTransform: 'uppercase' }}>
                      ✓ Learned
                    </span>
                  )}
                </div>
                {!skill.is_known && (
                  <GameButton
                    onClick={() => handleLearn(skill.name, selectedCategory)}
                    disabled={!skill.can_learn}
                    variant={skill.can_learn ? 'primary' : 'secondary'}
                    style={{ padding: '4px 10px', fontSize: '10px' }}
                  >
                    LEARN ({skill.required_exp})
                  </GameButton>
                )}
              </div>

              <div style={{
                color: '#888',
                fontSize: '12px',
                lineHeight: '1.4',
                fontStyle: 'italic',
                flex: 1,
              }}>
                {skill.description}
              </div>

              {!skill.is_known && !skill.can_learn && (
                <div style={{ color: '#ff4444', fontSize: '10px', fontFamily: 'monospace' }}>
                  Requires {skill.required_exp} {selectedCategory} XP
                </div>
              )}
            </div>
          ))}

          {selectedCategory && (!skill_tree[selectedCategory] || skill_tree[selectedCategory].length === 0) && (
            <div style={{ gridColumn: '1 / -1', textAlign: 'center', padding: '40px', color: '#666', fontStyle: 'italic' }}>
              No skills currently available in this discipline.
            </div>
          )}
        </div>

        <div style={{ display: 'flex', justifyContent: 'center', marginTop: '10px' }}>
          <GameButton onClick={onClose} variant="secondary">
            CLOSE BOOK
          </GameButton>
        </div>
      </div>
    </BaseDialog>
  )
}
