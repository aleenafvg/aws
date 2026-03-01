/**
 * audioUtils.js – Audio compression and format conversion utilities.
 * 
 * SECURITY: All audio processing is client-side only.
 * Processed audio is not persisted beyond the current session.
 */

/**
 * SUPPORTED_FORMATS – Audio formats supported for recording, in preference order.
 * webm/opus offers the best compression for speech.
 */
export const SUPPORTED_FORMATS = [
    'audio/webm;codecs=opus',
    'audio/webm',
    'audio/ogg;codecs=opus',
    'audio/mp4',
]

/**
 * getBestMimeType – Returns the best supported MIME type for recording.
 * Prefers webm/opus for optimal speech compression.
 * 
 * @returns {string} Best supported MIME type, or empty string for default
 */
export function getBestMimeType() {
    if (typeof MediaRecorder === 'undefined') return ''

    for (const format of SUPPORTED_FORMATS) {
        if (MediaRecorder.isTypeSupported(format)) {
            return format
        }
    }
    return ''
}

/**
 * getAudioDuration – Get the duration of an audio Blob in seconds.
 * 
 * @param {Blob} audioBlob - Audio data
 * @returns {Promise<number>} Duration in seconds
 */
export async function getAudioDuration(audioBlob) {
    return new Promise((resolve, reject) => {
        const audio = new Audio()
        const url = URL.createObjectURL(audioBlob)

        audio.addEventListener('loadedmetadata', () => {
            URL.revokeObjectURL(url)

            // Some browsers report Infinity for streaming formats
            if (audio.duration === Infinity) {
                audio.currentTime = Number.MAX_SAFE_INTEGER
                audio.addEventListener('timeupdate', function handler() {
                    audio.removeEventListener('timeupdate', handler)
                    resolve(audio.duration)
                    audio.currentTime = 0
                })
            } else {
                resolve(audio.duration)
            }
        })

        audio.addEventListener('error', () => {
            URL.revokeObjectURL(url)
            reject(new Error('Failed to load audio'))
        })

        audio.src = url
    })
}

/**
 * formatFileSize – Format bytes into human-readable string.
 * 
 * @param {number} bytes - File size in bytes
 * @returns {string} Formatted file size (e.g., "1.2 MB")
 */
export function formatFileSize(bytes) {
    if (bytes === 0) return '0 B'
    const k = 1024
    const sizes = ['B', 'KB', 'MB', 'GB']
    const i = Math.floor(Math.log(bytes) / Math.log(k))
    return `${parseFloat((bytes / Math.pow(k, i)).toFixed(1))} ${sizes[i]}`
}

/**
 * isAudioSupported – Check if the browser supports audio recording.
 * 
 * @returns {boolean} Whether MediaRecorder and getUserMedia are available
 */
export function isAudioSupported() {
    return !!(
        typeof navigator !== 'undefined' &&
        navigator.mediaDevices &&
        typeof navigator.mediaDevices.getUserMedia === 'function' &&
        typeof MediaRecorder !== 'undefined'
    )
}
