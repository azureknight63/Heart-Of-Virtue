export default function ActionButtons({ mode, location, onInventory }) {
  const explorationActions = [
    { label: 'Take', action: () => { } },
    { label: 'Examine', action: () => { } },
    { label: 'Inventory', action: onInventory },
    { label: 'Skills', action: () => { } },
  ]

  const combatActions = [
    { label: 'Attack', action: () => { } },
    { label: 'Defend', action: () => { } },
    { label: 'Skill', action: () => { } },
    { label: 'Retreat', action: () => { } },
    { label: 'Check', action: () => { } },
  ]

  const actions = mode === 'combat' ? combatActions : explorationActions

  return (
    <div className={`grid gap-1.5 bg-[rgba(0,0,0,0.3)] p-2.5 border-t border-[#333] ${mode === 'combat' ? 'grid-cols-3' : 'grid-cols-2'
      }`}>
      {actions.map((action, idx) => (
        <button
          key={idx}
          onClick={action.action}
          className="btn btn-secondary text-sm py-2.5 px-3 font-bold hover:bg-lime hover:text-black"
        >
          {action.label}
        </button>
      ))}
      <button className={`btn btn-primary text-sm py-2.5 px-3 font-bold ${mode === 'combat' ? 'col-span-3' : 'col-span-2'}`}>
        Save Game
      </button>
    </div>
  )
}
