import { useEffect, useState } from 'react'

/**
 * SplashScreen – Intro animation component.
 * Displays "Yojana-Setu" with a typewriter effect on a plain dark background.
 * Clean font, nothing else on screen.
 * Duration: ~2 seconds, then auto-transitions to main screen.
 * 
 * @param {Function} onComplete - Callback when splash animation finishes
 */
export default function SplashScreen({ onComplete }) {
    const [showText, setShowText] = useState(false)
    const [showSubtitle, setShowSubtitle] = useState(false)
    const [fadeOut, setFadeOut] = useState(false)

    useEffect(() => {
        // Start typewriter after a brief moment
        const showTimer = setTimeout(() => setShowText(true), 200)

        // Show subtitle after typewriter completes
        const subtitleTimer = setTimeout(() => setShowSubtitle(true), 1200)

        // Begin fade out
        const fadeTimer = setTimeout(() => setFadeOut(true), 2200)

        // Complete transition
        const completeTimer = setTimeout(() => onComplete(), 2700)

        return () => {
            clearTimeout(showTimer)
            clearTimeout(subtitleTimer)
            clearTimeout(fadeTimer)
            clearTimeout(completeTimer)
        }
    }, [onComplete])

    return (
        <div
            className={`fixed inset-0 z-50 flex flex-col items-center justify-center bg-surface-950 transition-opacity duration-500 ${fadeOut ? 'opacity-0' : 'opacity-100'
                }`}
        >
            {/* "Yojana-Setu" with typewriter animation */}
            {showText && (
                <div className="relative">
                    <h1
                        className="text-4xl md:text-7xl font-light tracking-[0.2em] text-white overflow-hidden whitespace-nowrap border-r-2 border-white animate-typewriter"
                        style={{
                            animationDuration: '1.2s',
                            animationTimingFunction: 'steps(11)',
                            animationFillMode: 'forwards',
                        }}
                    >
                        Yojana-Setu
                    </h1>
                </div>
            )}

            {/* Subtle subtitle */}
            {showSubtitle && (
                <p
                    className="mt-6 text-sm md:text-base tracking-[0.5em] uppercase text-white/30 font-light animate-fade-in"
                >
                    AI for Bharat
                </p>
            )}
        </div>
    )
}
