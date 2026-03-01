import { useState, useCallback } from 'react'
import MicButton from './MicButton'
import ResponseCard from './ResponseCard'
import ErrorDisplay from './ErrorDisplay'
import useVoiceRecorder from '../hooks/useVoiceRecorder'
import useApi from '../hooks/useApi'

/**
 * LANGUAGE_LABELS – Human-readable names for each supported language code.
 * Used to display detected language to the user.
 */
const LANGUAGE_LABELS = {
    'hi-IN': 'हिन्दी',
    'ta-IN': 'தமிழ்',
    'te-IN': 'తెలుగు',
    'mr-IN': 'मराठी',
    'bn-IN': 'বাংলা',
    'gu-IN': 'ગુજરાતી',
    'kn-IN': 'ಕನ್ನಡ',
    'ml-IN': 'മലയാളം',
    'pa-IN': 'ਪੰਜਾਬੀ',
    'en-IN': 'English',
}

/**
 * STATUS_MESSAGES – Native-language status messages for each supported language.
 * Displayed during processing so users see feedback in their own language.
 */
const STATUS_MESSAGES = {
    ready: {
        'en-IN': 'Tap the mic and speak your question',
        'hi-IN': 'माइक दबाएं और अपना सवाल बोलें',
        default: 'Tap the mic and speak your question',
    },
    listening: {
        'en-IN': 'Listening...',
        'hi-IN': 'सुन रहे हैं...',
        default: 'Listening...',
    },
    processing: {
        'en-IN': 'Finding your answer...',
        'hi-IN': 'आपका जवाब खोज रहे हैं...',
        default: 'Finding your answer...',
    },
}

/**
 * MainScreen – Primary voice interface.
 * Contains the mic button, status indicator, and response display.
 * No language dropdown, no text input — fully voice-driven.
 */
export default function MainScreen() {
    const [appState, setAppState] = useState('ready') // ready | listening | processing | result | error
    const [response, setResponse] = useState(null)
    const [error, setError] = useState(null)

    const { processQuery, isLoading } = useApi()

    /**
     * handleRecordingComplete – Called when voice recording finishes.
     * Sends audio blob to backend for processing.
     * @param {Blob} audioBlob - Recorded audio data
     */
    const handleRecordingComplete = useCallback(async (audioBlob) => {
        setAppState('processing')
        setError(null)
        setResponse(null)

        try {
            const result = await processQuery(audioBlob)
            setResponse(result)
            setAppState('result')
        } catch (err) {
            // SECURITY: Do not expose internal error details to the user
            console.error('[MainScreen] Query processing failed:', err?.message || err)
            setError(err?.userMessage || 'Something went wrong. Please try again.')
            setAppState('error')
        }
    }, [processQuery])

    /**
     * handleRecordingStart – Called when recording begins.
     */
    const handleRecordingStart = useCallback(() => {
        setAppState('listening')
        setResponse(null)
        setError(null)
    }, [])

    /**
     * handleRetry – Reset state and allow user to try again.
     */
    const handleRetry = useCallback(() => {
        setAppState('ready')
        setError(null)
        setResponse(null)
    }, [])

    const getStatusText = () => {
        const lang = response?.detected_language || 'default'
        const messages = STATUS_MESSAGES[appState] || STATUS_MESSAGES.ready
        return messages[lang] || messages.default
    }

    return (
        <div className="flex-1 flex flex-col items-center justify-between min-h-screen px-4 py-8 relative overflow-hidden">
            {/* Background decorative elements */}
            <div className="absolute inset-0 pointer-events-none overflow-hidden">
                <div className="absolute -top-40 -right-40 w-80 h-80 bg-primary-500/5 rounded-full blur-3xl" />
                <div className="absolute -bottom-40 -left-40 w-80 h-80 bg-accent-500/5 rounded-full blur-3xl" />
                <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[600px] bg-primary-600/3 rounded-full blur-3xl" />
            </div>

            {/* Header */}
            <header className="relative z-10 text-center animate-fade-in pt-4">
                <h1 className="text-2xl md:text-3xl font-semibold tracking-tight text-white">
                    Yojana<span className="text-primary-400">-</span>Setu
                </h1>
                <p className="mt-1 text-xs md:text-sm text-white/40 tracking-widest uppercase font-light">
                    AI for Bharat
                </p>
            </header>

            {/* Center area – Mic button + status */}
            <main className="relative z-10 flex flex-col items-center gap-8 flex-1 justify-center -mt-8">
                {/* Status text */}
                <p className={`text-sm md:text-base text-center transition-all duration-300 ${appState === 'listening'
                        ? 'text-danger-400 animate-pulse'
                        : appState === 'processing'
                            ? 'text-accent-400'
                            : 'text-white/50'
                    }`}>
                    {getStatusText()}
                </p>

                {/* Microphone button */}
                <MicButton
                    onRecordingStart={handleRecordingStart}
                    onRecordingComplete={handleRecordingComplete}
                    isProcessing={appState === 'processing'}
                    disabled={appState === 'processing'}
                />

                {/* Detected language badge */}
                {response?.detected_language && (
                    <div className="animate-fade-in-up flex items-center gap-2">
                        <span className="px-3 py-1 rounded-full glass text-xs font-medium text-primary-300">
                            {LANGUAGE_LABELS[response.detected_language] || response.detected_language}
                        </span>
                        {response.detected_language_confidence && (
                            <span className="text-xs text-white/30">
                                {(response.detected_language_confidence * 100).toFixed(0)}% confident
                            </span>
                        )}
                    </div>
                )}
            </main>

            {/* Response / Error area */}
            <footer className="relative z-10 w-full max-w-lg pb-4">
                {appState === 'result' && response && (
                    <ResponseCard response={response} onNewQuery={handleRetry} />
                )}

                {appState === 'error' && (
                    <ErrorDisplay message={error} onRetry={handleRetry} />
                )}
            </footer>

            {/* Bottom hint */}
            {appState === 'ready' && (
                <p className="relative z-10 text-[10px] text-white/20 text-center pb-2 animate-fade-in">
                    Speak in any Indian language • No typing needed
                </p>
            )}
        </div>
    )
}
