function SearchCard({
    query,
    loading,
    indexing,
    readyCount,
    provider,
    textareaRef,
    onQueryChange,
    onKeyDown,
    onSearch,
    onIndex
}) {
    return (
        <div className="card">
            <textarea
                ref={textareaRef}
                className="search-textarea"
                value={query}
                onChange={onQueryChange}
                onKeyDown={onKeyDown}
                placeholder="Введите вопрос по документации... (Enter для поиска, Shift+Enter для новой строки)"
                rows={1}
            />
            <div className="search-actions">
                <button
                    onClick={onSearch}
                    disabled={loading || !query.trim()}
                    className="btn btn-primary"
                >
                    {loading ? '🔍 Генерация ответа...' : '🚀 Найти ответ'}
                </button>
                <button
                    onClick={onIndex}
                    disabled={indexing}
                    className="btn btn-secondary"
                >
                    {indexing ? '⏳ Индексация...' : '🔄 Переиндексировать'}
                </button>
            </div>
            <div className="search-info">
                <span>📚 В индексе: <strong>{readyCount}</strong> документов</span>
                <span>⚡ Провайдер: <strong>{provider === 'yandex' ? 'Yandex AI Studio' : provider}</strong></span>
            </div>
        </div>
    )
}

export default SearchCard
