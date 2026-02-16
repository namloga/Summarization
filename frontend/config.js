// Конфигурация API
// Для деплоя: измените BASE_URL на URL backend (например: https://your-app.onrender.com)
const API_CONFIG = {
    BASE_URL: (typeof window !== 'undefined' && window.API_BASE_URL) ? window.API_BASE_URL : 'http://localhost:8000',
    ENDPOINTS: {
        HEALTH: '/health',
        SUMMARIZE: '/summarize',
        SUMMARIZE_FILE: '/summarize-file'
    }
};

// Проверка доступности API
async function testApiConnection() {
    try {
        const response = await fetch(`${API_CONFIG.BASE_URL}${API_CONFIG.ENDPOINTS.HEALTH}`);
        const result = await response.json();
        return result.status === 'ok';
    } catch (error) {
        console.error('Не удалось подключиться к API:', error);
        return false;
    }
}

// Экспорт в глобальную область видимости
if (typeof window !== 'undefined') {
    window.API_CONFIG = API_CONFIG;
    window.testApiConnection = testApiConnection;
}