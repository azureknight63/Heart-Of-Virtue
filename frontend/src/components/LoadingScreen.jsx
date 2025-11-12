export default function LoadingScreen() {
  return (
    <div className="w-screen h-screen bg-dark-900 flex items-center justify-center">
      <div className="text-center">
        <h1 className="text-4xl font-bold text-lime mb-8 animate-pulse-glow">
          Heart of Virtue
        </h1>
        <div className="flex justify-center items-center gap-2 mb-8">
          <div className="w-3 h-3 bg-lime rounded-full animate-bounce" style={{ animationDelay: '0s' }}></div>
          <div className="w-3 h-3 bg-lime rounded-full animate-bounce" style={{ animationDelay: '0.2s' }}></div>
          <div className="w-3 h-3 bg-lime rounded-full animate-bounce" style={{ animationDelay: '0.4s' }}></div>
        </div>
        <p className="text-cyan text-sm">Initializing game world...</p>
      </div>
    </div>
  )
}
