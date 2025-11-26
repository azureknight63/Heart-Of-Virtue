import { useState, useEffect } from 'react'
import apiEndpoints from '../api/endpoints'

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
        // Set default category if not set
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
        // Update local state with new data
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
      <div style={{
        backgroundColor: 'rgba(50, 20, 0, 0.4)',
        border: '2px solid #ffaa00',
        borderRadius: '6px',
        padding: '8px',
        color: '#ffaa00',
        fontFamily: 'monospace',
        textAlign: 'center',
        fontSize: '11px',
      }}>
        Loading skills...
      </div>
    )
  }

  if (error || !skillsData) {
    return (
      <div style={{
        backgroundColor: 'rgba(50, 20, 0, 0.4)',
        border: '2px solid #ffaa00',
        borderRadius: '6px',
        padding: '8px',
        color: '#ff0000',
        fontFamily: 'monospace',
        textAlign: 'center',
        fontSize: '11px',
      }}>
        <div style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          borderBottom: '2px solid #ffaa00',
          paddingBottom: '4px',
          marginBottom: '4px',
        }}>
          <div style={{ fontWeight: 'bold', fontSize: '13px', color: '#ffff00' }}>
            ⚡ SKILLS
          </div>
          <button
            onClick={onClose}
            style={{
              padding: '2px 6px',
              backgroundColor: '#cc4400',
              color: '#ffff00',
              border: '1px solid #ff6600',
              borderRadius: '3px',
              cursor: 'pointer',
              fontSize: '10px',
              fontFamily: 'monospace',
              fontWeight: 'bold',
            }}
          >
            ✕
          </button>
        </div>
        {error || 'No skill data available'}
      </div>
    )
  }

  const { skill_tree, skill_exp } = skillsData
  const categories = Object.keys(skill_tree || {})

  return (
    <div style={{
      backgroundColor: 'rgba(50, 20, 0, 0.3)',
      border: '2px solid #ffaa00',
      borderRadius: '6px',
      padding: '12px',
      display: 'flex',
      flexDirection: 'column',
      gap: '8px',
      maxHeight: '60vh',
    }}>
      {/* Header */}
      <div style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        borderBottom: '2px solid #ffaa00',
        paddingBottom: '4px',
        marginBottom: '2px',
      }}>
        <div style={{
          color: '#ffff00',
          fontWeight: 'bold',
          fontSize: '13px',
          fontFamily: 'monospace',
        }}>
          ⚡ SKILLS
        </div>
        <button
          onClick={onClose}
          style={{
            padding: '2px 6px',
            backgroundColor: '#cc4400',
            color: '#ffff00',
            border: '1px solid #ff6600',
            borderRadius: '3px',
            cursor: 'pointer',
            fontSize: '10px',
            fontFamily: 'monospace',
            fontWeight: 'bold',
          }}
          onMouseEnter={(e) => {
            e.target.style.backgroundColor = '#ff6600'
          }}
          onMouseLeave={(e) => {
            e.target.style.backgroundColor = '#cc4400'
          }}
        >
          ✕
        </button>
      </div>

      {/* Categories */}
      <div style={{
        display: 'flex',
        gap: '4px',
        overflowX: 'auto',
        paddingBottom: '4px',
        borderBottom: '1px solid #664400',
      }}>
        {categories.map(cat => (
          <button
            key={cat}
            onClick={() => setSelectedCategory(cat)}
            style={{
              padding: '4px 8px',
              backgroundColor: selectedCategory === cat ? '#ffaa00' : 'rgba(30, 15, 0, 0.5)',
              color: selectedCategory === cat ? '#000000' : '#ffaa00',
              border: '1px solid #ffaa00',
              borderRadius: '3px',
              cursor: 'pointer',
              fontSize: '10px',
              fontFamily: 'monospace',
              fontWeight: 'bold',
              whiteSpace: 'nowrap',
            }}
          >
            {cat}
          </button>
        ))}
      </div>

      {/* EXP Display */}
      {selectedCategory && (
        <div style={{
          color: '#00ff00',
          fontSize: '11px',
          fontFamily: 'monospace',
          textAlign: 'right',
          paddingRight: '4px',
        }}>
          EXP: {skill_exp[selectedCategory] || 0}
        </div>
      )}

      {/* Skills List */}
      <div style={{
        display: 'flex',
        flexDirection: 'column',
        gap: '4px',
        overflowY: 'auto',
        flex: 1,
      }}>
        {selectedCategory && skill_tree[selectedCategory]?.map((skill, idx) => (
          <div key={idx} style={{
            backgroundColor: skill.is_known ? 'rgba(0, 50, 0, 0.3)' : 'rgba(30, 15, 0, 0.3)',
            border: skill.is_known ? '1px solid #00ff00' : '1px solid #664400',
            borderRadius: '3px',
            padding: '6px',
            fontSize: '10px',
            fontFamily: 'monospace',
          }}>
            <div style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              marginBottom: '4px',
            }}>
              <div style={{
                color: skill.is_known ? '#00ff00' : '#ffff00',
                fontWeight: 'bold',
              }}>
                {skill.name} {skill.is_known && '(LEARNED)'}
              </div>
              {!skill.is_known && (
                <button
                  onClick={() => handleLearn(skill.name, selectedCategory)}
                  disabled={!skill.can_learn}
                  style={{
                    padding: '2px 6px',
                    backgroundColor: skill.can_learn ? '#00cc66' : '#333333',
                    color: skill.can_learn ? '#000000' : '#666666',
                    border: 'none',
                    borderRadius: '3px',
                    cursor: skill.can_learn ? 'pointer' : 'not-allowed',
                    fontSize: '9px',
                    fontWeight: 'bold',
                  }}
                >
                  LEARN ({skill.required_exp} XP)
                </button>
              )}
            </div>

            <div style={{
              color: '#cccccc',
              fontSize: '9px',
              fontStyle: 'italic',
              marginBottom: '2px',
            }}>
              {skill.description}
            </div>

            {!skill.is_known && !skill.can_learn && (
              <div style={{ color: '#ff4444', fontSize: '9px' }}>
                Requires {skill.required_exp} XP
              </div>
            )}
          </div>
        ))}

        {selectedCategory && (!skill_tree[selectedCategory] || skill_tree[selectedCategory].length === 0) && (
          <div style={{ color: '#888888', textAlign: 'center', padding: '10px' }}>
            No skills in this category.
          </div>
        )}
      </div>
    </div>
  )
}
