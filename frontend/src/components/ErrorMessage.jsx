function ErrorMessage({ message }) {
    if (!message) return null

    return (
        <div className="error">
            <span className="error-icon">⚠️</span>
            <span>{message}</span>
        </div>
    )
}

export default ErrorMessage
