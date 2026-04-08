"""HTML шаблоны для страниц статуса и дашборда."""


def format_uptime(seconds: float) -> str:
    if seconds < 60:
        return f"{int(seconds)} сек"
    elif seconds < 3600:
        return f"{int(seconds // 60)} мин"
    elif seconds < 86400:
        return f"{int(seconds // 3600)} ч {int((seconds % 3600) // 60)} мин"
    else:
        return f"{int(seconds // 86400)} д {int((seconds % 86400) // 3600)} ч"


def health_html(data: dict) -> str:
    return f"""
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>DocSearch — Статус системы</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 2rem;
        }}
        .container {{
            max-width: 600px;
            width: 100%;
        }}
        .card {{
            background: white;
            border-radius: 20px;
            padding: 3rem;
            box-shadow: 0 20px 60px rgba(0,0,0,0.15);
        }}
        .header {{
            text-align: center;
            margin-bottom: 2.5rem;
        }}
        .header h1 {{
            font-size: 2rem;
            color: #1f2937;
            margin-bottom: 0.5rem;
        }}
        .status-badge {{
            display: inline-flex;
            align-items: center;
            gap: 0.5rem;
            padding: 0.75rem 1.5rem;
            border-radius: 50px;
            font-weight: 600;
            font-size: 1.1rem;
            margin-top: 1rem;
        }}
        .status-badge.healthy {{
            background: #10b981;
            color: white;
            box-shadow: 0 4px 15px rgba(16, 185, 129, 0.4);
        }}
        .status-badge.unhealthy {{
            background: #ef4444;
            color: white;
            box-shadow: 0 4px 15px rgba(239, 68, 68, 0.4);
        }}
        .metrics {{
            display: grid;
            gap: 1.5rem;
        }}
        .metric {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 1.25rem 1.5rem;
            background: #f9fafb;
            border-radius: 12px;
            transition: transform 0.2s;
        }}
        .metric:hover {{
            transform: translateX(5px);
            background: #f3f4f6;
        }}
        .metric-label {{
            display: flex;
            align-items: center;
            gap: 0.75rem;
            color: #6b7280;
            font-weight: 500;
        }}
        .metric-icon {{
            font-size: 1.5rem;
        }}
        .metric-value {{
            font-size: 1.25rem;
            font-weight: 700;
            color: #1f2937;
        }}
        .footer {{
            text-align: center;
            margin-top: 2rem;
            padding-top: 1.5rem;
            border-top: 1px solid #e5e7eb;
            color: #9ca3af;
            font-size: 0.875rem;
        }}
        .footer a {{
            color: #667eea;
            text-decoration: none;
            font-weight: 500;
        }}
        .footer a:hover {{
            text-decoration: underline;
        }}
        .refresh {{
            display: block;
            margin: 1.5rem auto 0;
            padding: 0.75rem 2rem;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            border-radius: 10px;
            font-size: 1rem;
            font-weight: 600;
            cursor: pointer;
            transition: transform 0.2s, box-shadow 0.2s;
        }}
        .refresh:hover {{
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(102,126,234,0.4);
        }}
        @keyframes fadeIn {{
            from {{ opacity: 0; transform: translateY(10px); }}
            to {{ opacity: 1; transform: translateY(0); }}
        }}
        .card {{ animation: fadeIn 0.3s ease-out; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="card">
            <div class="header">
                <h1>🔍 DocSearch</h1>
                <p style="color: #6b7280;">Статус системы семантического поиска</p>
                <div class="status-badge {"healthy" if data["status"] == "healthy" else "unhealthy"}">
                    {"✅ Система работает" if data["status"] == "healthy" else "❌ Проблема"}
                </div>
            </div>

            <div class="metrics">
                <div class="metric">
                    <div class="metric-label">
                        <span class="metric-icon">📚</span>
                        <span>Проиндексировано документов</span>
                    </div>
                    <div class="metric-value">{data["indexed_documents"]:,}</div>
                </div>

                <div class="metric">
                    <div class="metric-label">
                        <span class="metric-icon">⚡</span>
                        <span>AI Провайдер</span>
                    </div>
                    <div class="metric-value" style="text-transform: capitalize;">{data["provider"]}</div>
                </div>

                <div class="metric">
                    <div class="metric-label">
                        <span class="metric-icon">⏱️</span>
                        <span>Аптайм</span>
                    </div>
                    <div class="metric-value">{format_uptime(data["uptime_seconds"])}</div>
                </div>

                <div class="metric">
                    <div class="metric-label">
                        <span class="metric-icon">🔄</span>
                        <span>Фоновая индексация</span>
                    </div>
                    <div class="metric-value" style="color: {"#10b981" if data["scheduler_running"] else "#ef4444"};">
                        {"✅ Активна" if data["scheduler_running"] else "⏸️ Остановлена"}
                    </div>
                </div>
            </div>

            <button class="refresh" onclick="location.reload()">🔄 Обновить</button>

            <div class="footer">
                <a href="/dashboard">📊 Полный дашборд</a> ·
                <a href="/api/health?format=json">📄 JSON API</a> ·
                <a href="/docs">📖 Swagger</a>
            </div>
        </div>
    </div>

    <script>
        setTimeout(() => location.reload(), 30000);
    </script>
</body>
</html>
    """


def health_error_html(error: str) -> str:
    return f"""
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>DocSearch — Ошибка</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 2rem;
        }}
        .card {{
            background: white;
            border-radius: 20px;
            padding: 3rem;
            box-shadow: 0 20px 60px rgba(0,0,0,0.15);
            text-align: center;
            max-width: 500px;
        }}
        .icon {{ font-size: 4rem; margin-bottom: 1rem; }}
        h1 {{ color: #ef4444; margin-bottom: 1rem; }}
        p {{ color: #6b7280; line-height: 1.6; }}
        .error {{
            background: #fee2e2;
            padding: 1rem;
            border-radius: 8px;
            margin-top: 1rem;
            color: #991b1b;
            font-family: monospace;
        }}
    </style>
</head>
<body>
    <div class="card">
        <div class="icon">❌</div>
        <h1>Система недоступна</h1>
        <p>Произошла ошибка при проверке статуса системы</p>
        <div class="error">{error}</div>
    </div>
</body>
</html>
    """


def dashboard_html() -> str:
    return """
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>DocSearch Dashboard</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 2rem;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
        }
        .header {
            text-align: center;
            color: white;
            margin-bottom: 2rem;
        }
        .header h1 {
            font-size: 2.5rem;
            margin-bottom: 0.5rem;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.2);
        }
        .header p {
            font-size: 1.1rem;
            opacity: 0.9;
        }
        .status-badge {
            display: inline-block;
            padding: 0.5rem 1.5rem;
            border-radius: 50px;
            font-weight: 600;
            margin-top: 1rem;
            font-size: 1.1rem;
        }
        .status-badge.healthy {
            background: #10b981;
            color: white;
            box-shadow: 0 4px 12px rgba(16, 185, 129, 0.4);
        }
        .status-badge.unhealthy {
            background: #ef4444;
            color: white;
            box-shadow: 0 4px 12px rgba(239, 68, 68, 0.4);
        }
        .cards {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 1.5rem;
            margin-bottom: 2rem;
        }
        .card {
            background: white;
            border-radius: 16px;
            padding: 2rem;
            box-shadow: 0 10px 30px rgba(0,0,0,0.1);
            transition: transform 0.2s, box-shadow 0.2s;
        }
        .card:hover {
            transform: translateY(-5px);
            box-shadow: 0 15px 40px rgba(0,0,0,0.15);
        }
        .card-icon {
            font-size: 2.5rem;
            margin-bottom: 1rem;
        }
        .card-label {
            color: #6b7280;
            font-size: 0.9rem;
            font-weight: 500;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            margin-bottom: 0.5rem;
        }
        .card-value {
            color: #1f2937;
            font-size: 2rem;
            font-weight: 700;
            margin-bottom: 0.25rem;
        }
        .card-subtext {
            color: #9ca3af;
            font-size: 0.85rem;
        }
        .progress-bar {
            width: 100%;
            height: 8px;
            background: #e5e7eb;
            border-radius: 4px;
            overflow: hidden;
            margin-top: 1rem;
        }
        .progress-fill {
            height: 100%;
            background: linear-gradient(90deg, #667eea, #764ba2);
            transition: width 0.3s;
        }
        .api-section {
            background: white;
            border-radius: 16px;
            padding: 2rem;
            box-shadow: 0 10px 30px rgba(0,0,0,0.1);
        }
        .api-section h2 {
            color: #1f2937;
            margin-bottom: 1.5rem;
            font-size: 1.5rem;
        }
        .endpoint {
            background: #f9fafb;
            border-left: 4px solid #667eea;
            padding: 1rem 1.5rem;
            margin-bottom: 1rem;
            border-radius: 8px;
        }
        .endpoint-method {
            display: inline-block;
            background: #667eea;
            color: white;
            padding: 0.25rem 0.75rem;
            border-radius: 4px;
            font-weight: 600;
            font-size: 0.85rem;
            margin-right: 0.5rem;
        }
        .endpoint-path {
            font-family: 'Courier New', monospace;
            color: #1f2937;
            font-weight: 600;
        }
        .endpoint-desc {
            color: #6b7280;
            margin-top: 0.5rem;
            font-size: 0.9rem;
        }
        .refresh-btn {
            position: fixed;
            bottom: 2rem;
            right: 2rem;
            background: white;
            border: none;
            border-radius: 50%;
            width: 60px;
            height: 60px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.2);
            cursor: pointer;
            font-size: 1.5rem;
            transition: transform 0.3s;
        }
        .refresh-btn:hover {
            transform: rotate(180deg);
        }
        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }
        .loading {
            animation: pulse 1.5s ease-in-out infinite;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🔍 DocSearch Dashboard</h1>
            <p>Мониторинг системы семантического поиска</p>
            <div id="statusBadge" class="status-badge loading">Загрузка...</div>
        </div>

        <div class="cards">
            <div class="card">
                <div class="card-icon">📚</div>
                <div class="card-label">Проиндексировано</div>
                <div class="card-value" id="docCount">—</div>
                <div class="card-subtext">документов в базе</div>
                <div class="progress-bar">
                    <div class="progress-fill" id="docProgress" style="width: 0%"></div>
                </div>
            </div>

            <div class="card">
                <div class="card-icon">⚡</div>
                <div class="card-label">AI Провайдер</div>
                <div class="card-value" id="provider">—</div>
                <div class="card-subtext">Yandex AI Studio</div>
            </div>

            <div class="card">
                <div class="card-icon">⏱️</div>
                <div class="card-label">Аптайм</div>
                <div class="card-value" id="uptime">—</div>
                <div class="card-subtext">время работы</div>
            </div>

            <div class="card">
                <div class="card-icon">🔄</div>
                <div class="card-label">Планировщик</div>
                <div class="card-value" id="scheduler">—</div>
                <div class="card-subtext" id="schedulerText">фоновая индексация</div>
            </div>
        </div>

        <div class="api-section">
            <h2>🔌 API Endpoints</h2>
            <div class="endpoint">
                <span class="endpoint-method">GET</span>
                <span class="endpoint-path">/api/health</span>
                <div class="endpoint-desc">Проверка статуса системы и получение метрик</div>
            </div>
            <div class="endpoint">
                <span class="endpoint-method">GET</span>
                <span class="endpoint-path">/api/ready</span>
                <div class="endpoint-desc">Количество проиндексированных документов</div>
            </div>
            <div class="endpoint">
                <span class="endpoint-method">POST</span>
                <span class="endpoint-path">/api/index</span>
                <div class="endpoint-desc">Запуск ручной индексации документов</div>
            </div>
            <div class="endpoint">
                <span class="endpoint-method">POST</span>
                <span class="endpoint-path">/api/query</span>
                <div class="endpoint-desc">Поиск и генерация ответа на вопрос</div>
            </div>
        </div>
    </div>

    <button class="refresh-btn" onclick="loadMetrics()" title="Обновить">🔄</button>

    <script>
        function formatUptime(seconds) {
            if (seconds < 60) return Math.round(seconds) + 'с';
            if (seconds < 3600) return Math.round(seconds / 60) + 'м';
            if (seconds < 86400) return Math.round(seconds / 3600) + 'ч';
            return Math.round(seconds / 86400) + 'д';
        }

        async function loadMetrics() {
            try {
                const response = await fetch('/api/health');
                const data = await response.json();

                const badge = document.getElementById('statusBadge');
                badge.className = 'status-badge ' + (data.status === 'healthy' ? 'healthy' : 'unhealthy');
                badge.textContent = data.status === 'healthy' ? '✅ Система работает' : '❌ Проблема';

                document.getElementById('docCount').textContent = data.indexed_documents.toLocaleString();
                document.getElementById('docProgress').style.width = Math.min(data.indexed_documents / 10, 100) + '%';

                document.getElementById('provider').textContent = data.provider.charAt(0).toUpperCase() + data.provider.slice(1);

                document.getElementById('uptime').textContent = formatUptime(data.uptime_seconds);

                document.getElementById('scheduler').textContent = data.scheduler_running ? '✅ Активен' : '⏸️ Остановлен';
                document.getElementById('schedulerText').textContent = data.scheduler_running ? 'индексация по расписанию' : 'не запущен';
            } catch (error) {
                document.getElementById('statusBadge').className = 'status-badge unhealthy';
                document.getElementById('statusBadge').textContent = '❌ Нет связи';
            }
        }

        loadMetrics();
        setInterval(loadMetrics, 30000);
    </script>
</body>
</html>
    """
