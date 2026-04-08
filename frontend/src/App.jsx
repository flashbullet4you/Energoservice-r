import { useState, useEffect, useRef } from 'react'
import './App.css'
import Header from './components/Header'
import SearchCard from './components/SearchCard'
import ErrorMessage from './components/ErrorMessage'
import ResultCard from './components/ResultCard'

function App() {
    const [query, setQuery] = useState('')
    const [result, setResult] = useState(null)
    const [loading, setLoading] = useState(false)
    const [indexing, setIndexing] = useState(false)
    const [error, setError] = useState('')
    const [readyCount, setReadyCount] = useState(0)
    const [provider, setProvider] = useState('yandex')
    const textareaRef = useRef(null)

    useEffect(() => {
        fetch('/api/ready').then(r => r.json()).then(d => setReadyCount(d.indexed_count || 0)).catch(() => { })
        fetch('/api/health').then(r => r.json()).then(d => setProvider(d.provider || 'yandex')).catch(() => { })
    }, [result])

    const handleSearch = async () => {
        if (!query.trim()) return
        setLoading(true); setError(''); setResult(null)
        try {
            const res = await fetch('/api/query', {
                method: 'POST', headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ question: query })
            })
            const data = await res.json()
            if (!res.ok) throw new Error(data.detail || 'Ошибка сервера')
            setResult(data)
            setQuery('')
            if (textareaRef.current) textareaRef.current.style.height = 'auto'
        } catch (err) { setError(err.message) }
        finally { setLoading(false) }
    }

    const handleKeyDown = (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault()
            handleSearch()
        }
    }

    const handleTextareaChange = (e) => {
        setQuery(e.target.value)
        e.target.style.height = 'auto'
        e.target.style.height = e.target.scrollHeight + 'px'
    }

    const handleIndex = async () => {
        setIndexing(true); setError('')
        try {
            const res = await fetch('/api/index', { method: 'POST' })
            const data = await res.json()
            if (!res.ok) throw new Error(data.detail || 'Ошибка индексации')
            setResult({ answer: `✅ Индексация завершена. Обработано файлов: ${data.indexed_files}`, sources: [] })
            fetch('/api/ready').then(r => r.json()).then(d => setReadyCount(d.indexed_count || 0))
        } catch (err) { setError(err.message) }
        finally { setIndexing(false) }
    }

    return (
        <div className="app">
            <div className="app-inner">
                <Header />
                <SearchCard
                    query={query}
                    loading={loading}
                    indexing={indexing}
                    readyCount={readyCount}
                    provider={provider}
                    textareaRef={textareaRef}
                    onQueryChange={handleTextareaChange}
                    onKeyDown={handleKeyDown}
                    onSearch={handleSearch}
                    onIndex={handleIndex}
                />
                <ErrorMessage message={error} />
                <ResultCard result={result} />
            </div>
        </div>
    )
}

export default App
