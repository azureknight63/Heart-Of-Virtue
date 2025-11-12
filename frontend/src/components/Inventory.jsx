export default function Inventory({ items, onClose }) {
  return (
    <div className="bg-[rgba(50,20,0,0.2)] border border-[#cc8800] rounded px-2 py-1.5 max-h-40 overflow-y-auto">
      <div className="flex justify-between items-center mb-1.5">
        <div className="text-[#ffaa00] font-bold text-xs">📦 Full Inventory</div>
        <button onClick={onClose} className="text-[#ff6600] text-xs hover:text-[#ff8844]">✕</button>
      </div>
      <div className="text-[#ffcc00] text-xs space-y-0.5">
        {items?.map((item, idx) => (
          <div key={idx} className="py-0.5 border-b border-[#333] last:border-0 flex justify-between">
            <span>{item.name}</span>
            {item.quantity > 1 && <span className="text-[#ffaa00]">x{item.quantity}</span>}
          </div>
        ))}
        {!items || items.length === 0 && (
          <p className="text-[#ff6600] italic">Your inventory is empty...</p>
        )}
      </div>
    </div>
  )
}
