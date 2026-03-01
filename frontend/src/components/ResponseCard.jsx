import { useRef, useState, useEffect } from 'react'

/**
 * ResponseCard – Displays the AI response with native text and audio playback.
 * Shows: response text, audio player, scheme ID, and a "New Query" button.
 * 
 * @param {Object} response - API response object
 * @param {Function} onNewQuery - Callback to reset for a new query
 */
export default function ResponseCard({ response, onNewQuery }) {
    const audioRef = useRef(null)
    const [isPlaying, setIsPlaying] = useState(false)
    const [audioLoaded, setAudioLoaded] = useState(false)
    const [audioError, setAudioError] = useState(false)

    // Auto-play audio response when available
    useEffect(() => {
        if (response?.audio_response_url && audioRef.current) {
            audioRef.current.play().catch(() => {
                // Auto-play may be blocked; user can tap play manually
                console.warn('[ResponseCard] Auto-play blocked by browser policy')
            })
        }
    }, [response?.audio_response_url])

    const toggleAudio = () => {
        if (!audioRef.current) return
        if (isPlaying) {
            audioRef.current.pause()
        } else {
            audioRef.current.play().catch(console.error)
        }
    }

    // INPUT VALIDATION: Bail out gracefully if response is malformed
    if (!response || typeof response !== 'object') {
        return null
    }

    return (
        <div className="glass rounded-2xl p-5 md:p-6 animate-slide-up space-y-4">
            {/* Response text in native language */}
            {response.ai_response_text_native && (
                <div className="space-y-2">
                    <p className="text-base md:text-lg leading-relaxed text-white/90 font-medium">
                        {response.ai_response_text_native}
                    </p>

                    {/* English translation (meta) */}
                    {response.user_intent_translated && (
                        <p className="text-xs text-white/30 italic">
                            Query: "{response.user_intent_translated}"
                        </p>
                    )}
                </div>
            )}

            {/* Audio player */}
            {response.audio_response_url && (
                <div className="flex items-center gap-3 p-3 rounded-xl bg-white/5">
                    <button
                        id="audio-play-button"
                        onClick={toggleAudio}
                        aria-label={isPlaying ? 'Pause audio' : 'Play audio'}
                        className="w-10 h-10 rounded-full bg-primary-500/20 flex items-center justify-center hover:bg-primary-500/30 transition-colors cursor-pointer"
                    >
                        {isPlaying ? (
                            <svg className="w-5 h-5 text-primary-300" fill="currentColor" viewBox="0 0 24 24">
                                <rect x="6" y="4" width="4" height="16" rx="1" />
                                <rect x="14" y="4" width="4" height="16" rx="1" />
                            </svg>
                        ) : (
                            <svg className="w-5 h-5 text-primary-300 ml-0.5" fill="currentColor" viewBox="0 0 24 24">
                                <path d="M8 5v14l11-7z" />
                            </svg>
                        )}
                    </button>

                    <div className="flex-1">
                        <div className="text-xs text-white/40">
                            {isPlaying ? 'Playing response...' : 'Tap to listen'}
                        </div>
                        {/* Hidden native audio element */}
                        <audio
                            ref={audioRef}
                            src={response.audio_response_url}
                            onPlay={() => setIsPlaying(true)}
                            onPause={() => setIsPlaying(false)}
                            onEnded={() => setIsPlaying(false)}
                            onCanPlayThrough={() => setAudioLoaded(true)}
                            onError={() => setAudioError(true)}
                            preload="auto"
                        />
                    </div>

                    {audioError && (
                        <span className="text-xs text-danger-400">Audio unavailable</span>
                    )}
                </div>
            )}

            {/* Scheme reference */}
            {response.relevant_scheme_id && (
                <div className="flex items-center gap-2 text-xs text-white/30">
                    <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                    <span>Scheme: {response.relevant_scheme_id}</span>
                </div>
            )}

            {/* New query button */}
            <button
                id="new-query-button"
                onClick={onNewQuery}
                className="w-full mt-2 py-2.5 rounded-xl bg-white/5 hover:bg-white/10 text-sm text-white/60 hover:text-white/80 transition-all duration-200 cursor-pointer"
            >
                Ask another question
            </button>
        </div>
    )
}
