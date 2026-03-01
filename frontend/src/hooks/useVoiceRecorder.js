import { useState, useRef, useCallback, useEffect } from 'react'

/**
 * useVoiceRecorder – Custom hook for voice recording with MediaRecorder API.
 * 
 * Features:
 * - Max recording duration (default 15s per PRD)
 * - Simple energy-based Voice Activity Detection for visual feedback
 * - Auto-stop when max duration reached
 * - Returns audio as Blob
 * 
 * SECURITY: Only accesses microphone with explicit user interaction (button click).
 * No audio data is persisted client-side.
 * 
 * @param {Object} options
 * @param {number} options.maxDuration - Maximum recording duration in ms (default: 15000)
 * @param {Function} options.onRecordingComplete - Callback with audio Blob when recording finishes
 */
export default function useVoiceRecorder({ maxDuration = 15000, onRecordingComplete }) {
    const [isRecording, setIsRecording] = useState(false)
    const [audioLevel, setAudioLevel] = useState(0)
    const [error, setError] = useState(null)

    const mediaRecorderRef = useRef(null)
    const audioChunksRef = useRef([])
    const streamRef = useRef(null)
    const analyserRef = useRef(null)
    const animationFrameRef = useRef(null)
    const maxDurationTimerRef = useRef(null)

    /**
     * Cleanup all media resources.
     * Ensures no lingering microphone access or memory leaks.
     */
    const cleanup = useCallback(() => {
        // Stop animation frame for audio level monitoring
        if (animationFrameRef.current) {
            cancelAnimationFrame(animationFrameRef.current)
            animationFrameRef.current = null
        }

        // Clear max duration timer
        if (maxDurationTimerRef.current) {
            clearTimeout(maxDurationTimerRef.current)
            maxDurationTimerRef.current = null
        }

        // Stop all media tracks (releases microphone)
        if (streamRef.current) {
            streamRef.current.getTracks().forEach((track) => track.stop())
            streamRef.current = null
        }

        analyserRef.current = null
        setAudioLevel(0)
    }, [])

    /**
     * Monitor audio levels for visual feedback (Voice Activity Detection).
     * Uses Web Audio API AnalyserNode to get frequency data.
     */
    const monitorAudioLevel = useCallback(() => {
        if (!analyserRef.current) return

        const analyser = analyserRef.current
        const dataArray = new Uint8Array(analyser.frequencyBinCount)

        const tick = () => {
            analyser.getByteFrequencyData(dataArray)
            // Calculate average volume level (0 to 1)
            const average = dataArray.reduce((sum, val) => sum + val, 0) / dataArray.length
            const normalized = Math.min(average / 128, 1) // Normalize to 0-1
            setAudioLevel(normalized)
            animationFrameRef.current = requestAnimationFrame(tick)
        }

        tick()
    }, [])

    /**
     * startRecording – Request microphone access and begin recording.
     * Uses webm/opus format for good compression on supported browsers,
     * falls back to default format otherwise.
     */
    const startRecording = useCallback(async () => {
        setError(null)
        audioChunksRef.current = []

        try {
            // REQUEST MICROPHONE – only happens on explicit user click
            const stream = await navigator.mediaDevices.getUserMedia({
                audio: {
                    echoCancellation: true,
                    noiseSuppression: true,
                    sampleRate: 16000, // Good quality for speech recognition
                },
            })
            streamRef.current = stream

            // Set up audio analysis for voice activity visual feedback
            const audioContext = new (window.AudioContext || window.webkitAudioContext)()
            const source = audioContext.createMediaStreamSource(stream)
            const analyser = audioContext.createAnalyser()
            analyser.fftSize = 256
            source.connect(analyser)
            analyserRef.current = analyser

            // Determine best MIME type for recording
            const mimeType = MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
                ? 'audio/webm;codecs=opus'
                : MediaRecorder.isTypeSupported('audio/webm')
                    ? 'audio/webm'
                    : ''

            const options = mimeType ? { mimeType } : {}
            const mediaRecorder = new MediaRecorder(stream, options)
            mediaRecorderRef.current = mediaRecorder

            mediaRecorder.ondataavailable = (e) => {
                if (e.data.size > 0) {
                    audioChunksRef.current.push(e.data)
                }
            }

            mediaRecorder.onstop = () => {
                const chunks = audioChunksRef.current
                if (chunks.length > 0) {
                    const blob = new Blob(chunks, {
                        type: mimeType || 'audio/webm',
                    })

                    // INPUT VALIDATION: Ensure blob is not empty before sending
                    if (blob.size > 0) {
                        onRecordingComplete?.(blob)
                    } else {
                        setError('No audio captured. Please try again.')
                    }
                }
                cleanup()
                setIsRecording(false)
            }

            mediaRecorder.onerror = (e) => {
                console.error('[useVoiceRecorder] MediaRecorder error:', e.error?.message)
                setError('Recording failed. Please try again.')
                cleanup()
                setIsRecording(false)
            }

            // Start recording with 250ms timeslice for chunked data
            mediaRecorder.start(250)
            setIsRecording(true)

            // Start monitoring audio levels for visual feedback
            monitorAudioLevel()

            // Auto-stop after max duration (15 seconds per PRD)
            maxDurationTimerRef.current = setTimeout(() => {
                if (mediaRecorderRef.current?.state === 'recording') {
                    mediaRecorderRef.current.stop()
                }
            }, maxDuration)
        } catch (err) {
            // Handle microphone permission denial gracefully
            if (err.name === 'NotAllowedError') {
                setError('Microphone access denied. Please allow microphone access to use this app.')
            } else if (err.name === 'NotFoundError') {
                setError('No microphone found. Please connect a microphone.')
            } else {
                setError('Could not access microphone. Please try again.')
            }
            console.error('[useVoiceRecorder] Error starting recording:', err?.message)
            cleanup()
            throw err
        }
    }, [maxDuration, onRecordingComplete, monitorAudioLevel, cleanup])

    /**
     * stopRecording – Stop the current recording manually.
     */
    const stopRecording = useCallback(() => {
        if (mediaRecorderRef.current?.state === 'recording') {
            mediaRecorderRef.current.stop()
        }
    }, [])

    // Cleanup on unmount
    useEffect(() => {
        return () => cleanup()
    }, [cleanup])

    return {
        isRecording,
        startRecording,
        stopRecording,
        audioLevel,
        error,
    }
}
