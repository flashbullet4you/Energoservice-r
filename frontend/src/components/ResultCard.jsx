function ResultCard({ result }) {
    if (!result) return null

    return (
        <div className="result">
            <h3 className="result-title">
                <span>💡</span> Ответ:
            </h3>
            <div className="result-text">
                {result.answer}
            </div>
            {result.sources?.length > 0 && (
                <div className="result-sources">
                    <h4>📄 Источники:</h4>
                    <div className="sources-list">
                        {result.sources.map((src, i) => (
                            <span
                                key={i}
                                className="source-tag"
                                title={src}
                            >
                                📎 {src.split(/[\\/]/).pop()}
                            </span>
                        ))}
                    </div>
                </div>
            )}
        </div>
    )
}

export default ResultCard
