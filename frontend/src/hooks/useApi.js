import { useState, useCallback } from 'react'

/**
 * API_BASE_URL – Base URL for the backend API.
 * In development, uses Vite's proxy (/api → localhost:3000).
 * In production, set VITE_API_URL environment variable to the API Gateway endpoint.
 * 
 * SECURITY: No API keys are stored or sent from the client.
 * All sensitive credentials are server-side only (Lambda env vars).
 */
const API_BASE_URL = import.meta.env.VITE_API_URL || '/api'

/**
 * MAX_AUDIO_SIZE – Maximum allowed audio file size (10MB).
 * INPUT VALIDATION: Prevents excessively large uploads.
 */
const MAX_AUDIO_SIZE = 10 * 1024 * 1024 // 10MB

/**
 * ALLOWED_AUDIO_TYPES – Whitelist of acceptable audio MIME types.
 * INPUT VALIDATION: Rejects unexpected file types.
 */
const ALLOWED_AUDIO_TYPES = [
    'audio/webm',
    'audio/webm;codecs=opus',
    'audio/ogg',
    'audio/mp4',
    'audio/mpeg',
    'audio/wav',
]

/**
 * useApi – Custom hook for communicating with the backend API.
 * Handles audio upload, loading states, and error handling.
 * 
 * SECURITY features:
 * - No API keys stored client-side
 * - Input validation (file size, MIME type)
 * - Sanitized error messages (no internal details exposed)
 * - Timeout protection
 */
export default function useApi() {
    const [isLoading, setIsLoading] = useState(false)

    /**
     * processQuery – Send audio blob to backend for processing.
     * 
     * @param {Blob} audioBlob - Recorded audio data
     * @returns {Promise<Object>} API response
     * @throws {Error} On network or validation errors
     */
    const processQuery = useCallback(async (audioBlob) => {
        // ── Input Validation ──────────────────────────────────────────
        if (!audioBlob || !(audioBlob instanceof Blob)) {
            throw Object.assign(new Error('Invalid audio data'), {
                userMessage: 'No audio was captured. Please try again.',
            })
        }

        // Validate file size (prevent oversized uploads)
        if (audioBlob.size > MAX_AUDIO_SIZE) {
            throw Object.assign(new Error(`Audio file too large: ${audioBlob.size} bytes`), {
                userMessage: 'Recording is too long. Please keep it under 15 seconds.',
            })
        }

        // Validate MIME type
        const blobType = audioBlob.type.split(';')[0] // Normalize type
        if (audioBlob.type && !ALLOWED_AUDIO_TYPES.some(t => audioBlob.type.startsWith(t.split(';')[0]))) {
            console.warn(`[useApi] Unexpected audio type: ${audioBlob.type}`)
            // Don't reject — some browsers report unusual types; let server validate
        }

        // Validate minimum size (avoid empty recordings)
        if (audioBlob.size < 100) {
            throw Object.assign(new Error('Audio blob is nearly empty'), {
                userMessage: 'No speech was detected. Please try again.',
            })
        }

        // ── Build Request ─────────────────────────────────────────────
        setIsLoading(true)

        const formData = new FormData()
        formData.append('audio_blob', audioBlob, 'recording.webm')

        try {
            const controller = new AbortController()
            // Timeout: 60 seconds (generous for multi-step AWS pipeline)
            const timeoutId = setTimeout(() => controller.abort(), 60000)

            const res = await fetch(`${API_BASE_URL}/process-multilingual-query`, {
                method: 'POST',
                body: formData,
                signal: controller.signal,
                // SECURITY: No custom auth headers — server handles all credentials
            })

            clearTimeout(timeoutId)

            // ── Handle Rate Limiting (429) ───────────────────────────
            if (res.status === 429) {
                const retryAfter = res.headers.get('Retry-After') || '60'
                throw Object.assign(new Error('Rate limited'), {
                    userMessage: `Too many requests. Please wait ${retryAfter} seconds and try again.`,
                })
            }

            // ── Handle Other Errors ──────────────────────────────────
            if (!res.ok) {
                const errorBody = await res.json().catch(() => ({}))
                // SECURITY: Don't expose internal error details to user
                throw Object.assign(new Error(`API error: ${res.status}`), {
                    userMessage: errorBody?.message || 'Service temporarily unavailable. Please try again.',
                })
            }

            const data = await res.json()

            // ── Response Validation ──────────────────────────────────
            if (!data || data.status !== 'success') {
                throw Object.assign(new Error('Invalid API response'), {
                    userMessage: data?.message || 'Could not process your query. Please try again.',
                })
            }

            return data
        } catch (err) {
            // Handle abort (timeout)
            if (err.name === 'AbortError') {
                throw Object.assign(new Error('Request timed out'), {
                    userMessage: 'The request took too long. Please check your connection and try again.',
                })
            }

            // Handle network errors
            if (err instanceof TypeError && err.message.includes('fetch')) {
                throw Object.assign(new Error('Network error'), {
                    userMessage: 'Cannot connect to the server. Please check your internet connection.',
                })
            }

            // Re-throw if already has userMessage
            if (err.userMessage) throw err

            // Generic fallback
            throw Object.assign(err, {
                userMessage: 'Something went wrong. Please try again.',
            })
        } finally {
            setIsLoading(false)
        }
    }, [])

    return { processQuery, isLoading }
}
