import { useState, useCallback, useRef, useEffect } from 'react'
import useVoiceRecorder from '../hooks/useVoiceRecorder'

/**
 * MicButton – Animated circular microphone button.
 * Visual states: idle (pulse glow) → recording (red pulse) → processing (spin)
 * Press to start recording, press again or auto-stop after 15s.
 * 
 * @param {Function} onRecordingStart - Called when recording begins
 * @param {Function} onRecordingComplete - Called with audio Blob when recording ends
 * @param {boolean} isProcessing - Whether backend is processing the query
 * @param {boolean} disabled - Whether button interactions are disabled
 */
export default function MicButton({ onRecordingStart, onRecordingComplete, isProcessing, disabled }) {
    const {
        isRecording,
        startRecording,
        stopRecording,
        audioLevel,
        error: recorderError,
    } = useVoiceRecorder({
        maxDuration: 15000, // 15 seconds max per PRD
        onRecordingComplete,
    })

    const handleClick = useCallback(async () => {
        if (disabled) return

        if (isRecording) {
            stopRecording()
        } else {
            try {
                await startRecording()
                onRecordingStart?.()
            } catch (err) {
                console.error('[MicButton] Failed to start recording:', err?.message)
            }
        }
    }, [disabled, isRecording, startRecording, stopRecording, onRecordingStart])

    // Dynamic ring scale based on audio level (voice activity visual feedback)
    const ringScale = isRecording ? 1 + (audioLevel * 0.5) : 1

    return (
        <div className="relative flex items-center justify-center">
            {/* Outer animated ring */}
            <div
                className={`absolute rounded-full transition-all duration-200 ${isRecording
                        ? 'w-36 h-36 md:w-44 md:h-44 bg-danger-500/10 animate-recording-pulse'
                        : isProcessing
                            ? 'w-36 h-36 md:w-44 md:h-44 bg-primary-500/10 animate-spin-slow'
                            : 'w-32 h-32 md:w-40 md:h-40 bg-primary-500/5'
                    }`}
                style={isRecording ? { transform: `scale(${ringScale})` } : {}}
            />

            {/* Middle ring */}
            <div
                className={`absolute rounded-full transition-all duration-300 ${isRecording
                        ? 'w-28 h-28 md:w-36 md:h-36 border-2 border-danger-400/30'
                        : isProcessing
                            ? 'w-28 h-28 md:w-36 md:h-36 border-2 border-primary-400/20'
                            : 'w-28 h-28 md:w-36 md:h-36 border border-primary-500/10'
                    }`}
            />

            {/* Main button */}
            <button
                id="mic-button"
                onClick={handleClick}
                disabled={disabled}
                aria-label={isRecording ? 'Stop recording' : 'Start recording'}
                className={`relative z-10 w-20 h-20 md:w-24 md:h-24 rounded-full flex items-center justify-center transition-all duration-300 cursor-pointer
          ${isRecording
                        ? 'bg-gradient-to-br from-danger-400 to-danger-500 shadow-lg shadow-danger-500/30'
                        : isProcessing
                            ? 'bg-gradient-to-br from-primary-600 to-primary-700 cursor-wait'
                            : 'bg-gradient-to-br from-primary-500 to-primary-600 shadow-lg shadow-primary-500/20 hover:shadow-primary-500/40 hover:scale-105 active:scale-95 animate-pulse-glow'
                    }
          ${disabled && !isProcessing ? 'opacity-50 cursor-not-allowed' : ''}
        `}
            >
                {isProcessing ? (
                    /* Processing spinner */
                    <svg className="w-8 h-8 md:w-10 md:h-10 text-white animate-spin" fill="none" viewBox="0 0 24 24">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" />
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                    </svg>
                ) : (
                    /* Microphone icon */
                    <svg
                        className={`w-8 h-8 md:w-10 md:h-10 text-white transition-transform duration-200 ${isRecording ? 'scale-110' : ''
                            }`}
                        fill="currentColor"
                        viewBox="0 0 24 24"
                    >
                        {isRecording ? (
                            /* Stop icon (square) when recording */
                            <rect x="6" y="6" width="12" height="12" rx="2" />
                        ) : (
                            /* Mic icon when idle */
                            <path d="M12 14c1.66 0 3-1.34 3-3V5c0-1.66-1.34-3-3-3S9 3.34 9 5v6c0 1.66 1.34 3 3 3zm5.91-3c-.49 0-.9.36-.98.85C16.52 14.2 14.47 16 12 16s-4.52-1.8-4.93-4.15c-.08-.49-.49-.85-.98-.85-.61 0-1.09.54-1 1.14.49 3 2.89 5.35 5.91 5.78V20c0 .55.45 1 1 1s1-.45 1-1v-2.08c3.02-.43 5.42-2.78 5.91-5.78.1-.6-.39-1.14-1-1.14z" />
                        )}
                    </svg>
                )}
            </button>

            {/* Recording timer indicator */}
            {isRecording && (
                <div className="absolute -bottom-8 left-1/2 -translate-x-1/2">
                    <span className="inline-flex items-center gap-1.5 text-xs text-danger-400">
                        <span className="w-1.5 h-1.5 rounded-full bg-danger-400 animate-pulse" />
                        Recording
                    </span>
                </div>
            )}
        </div>
    )
}
