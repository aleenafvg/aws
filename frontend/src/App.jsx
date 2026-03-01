import { useState, useEffect, useCallback } from 'react'
import SplashScreen from './components/SplashScreen'
import MainScreen from './components/MainScreen'

/**
 * App – Root component managing screen state transitions.
 * Flow: splash → main
 * The splash screen shows "1598" with typewriter animation for ~2 seconds,
 * then transitions to the main voice interface.
 */
function App() {
  const [showSplash, setShowSplash] = useState(true)

  const handleSplashComplete = useCallback(() => {
    setShowSplash(false)
  }, [])

  return (
    <div className="min-h-screen flex flex-col">
      {showSplash ? (
        <SplashScreen onComplete={handleSplashComplete} />
      ) : (
        <MainScreen />
      )}
    </div>
  )
}

export default App
