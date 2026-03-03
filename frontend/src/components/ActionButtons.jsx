// TODO: This component is a placeholder/stub. All action callbacks are currently no-ops.
// Wire up these actions or replace with the working ActionsPanel / CombatMovePanel components.
export default function ActionButtons({ mode, location, onInventory }) {
  const explorationActions = [
    { label: 'Take', action: () => { } },      // TODO: implement
    { label: 'Examine', action: () => { } },   // TODO: implement
    { label: 'Inventory', action: onInventory },
    { label: 'Skills', action: () => { } },    // TODO: implement
  ]

  const combatActions = [
    { label: 'Attack', action: () => { } },    // TODO: implement
    { label: 'Defend', action: () => { } },    // TODO: implement
    { label: 'Skill', action: () => { } },     // TODO: implement
    { label: 'Retreat', action: () => { } },   // TODO: implement
    { label: 'Check', action: () => { } },     // TODO: implement
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
      {/* TODO: wire up Save Game onClick */}
      <button className={`btn btn-primary text-sm py-2.5 px-3 font-bold ${mode === 'combat' ? 'col-span-3' : 'col-span-2'}`}>
        Save Game
      </button>
    </div>
  )
}

