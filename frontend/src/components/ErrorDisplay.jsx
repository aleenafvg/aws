/**
 * ErrorDisplay – Graceful error message with retry button.
 * Keeps the user experience friendly even when things go wrong.
 * 
 * @param {string} message - Error message to display
 * @param {Function} onRetry - Callback to retry the query
 */
export default function ErrorDisplay({ message, onRetry }) {
    return (
        <div className="glass rounded-2xl p-5 md:p-6 animate-slide-up text-center space-y-4">
            {/* Error icon */}
            <div className="flex justify-center">
                <div className="w-14 h-14 rounded-full bg-danger-500/10 flex items-center justify-center">
                    <svg className="w-7 h-7 text-danger-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            strokeWidth={1.5}
                            d="M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z"
                        />
                    </svg>
                </div>
            </div>

            {/* Error message – SECURITY: only show user-safe messages */}
            <p className="text-sm text-white/60 leading-relaxed">
                {message || 'Something went wrong. Please try again.'}
            </p>

            {/* Retry button */}
            <button
                id="retry-button"
                onClick={onRetry}
                className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-primary-600/20 hover:bg-primary-600/30 text-sm text-primary-300 hover:text-primary-200 transition-all duration-200 cursor-pointer"
            >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                </svg>
                Try again
            </button>
        </div>
    )
}
