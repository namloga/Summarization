const input = document.getElementById('inputText');
const output = document.getElementById('outputText');
const loading = document.getElementById('loading');
const clearBtn = document.getElementById('clearBtn');
const uploadBtn = document.getElementById('uploadBtn');
const fileInput = document.getElementById('fileInput');

const API_BASE = window.API_CONFIG?.BASE_URL || 'http://localhost:8000';
window.lastCsvCount = null;

input.addEventListener('input', () => {
    document.getElementById('inputCount').textContent =
        'Слова: ' + input.value.trim().split(/\s+/).filter(Boolean).length;
    if (input.value.length > 0) {
        clearBtn.classList.remove('hidden');
    } else {
        clearBtn.classList.add('hidden');
    }
});
function clearInput() {
    input.value = '';
    input.dispatchEvent(new Event('input'));
    input.focus();
}

async function startProcessing() {
    const text = input.value.trim();
    if (!text) {
        alert('Введите текст для суммаризации.');
        return;
    }

    loading.style.display = 'flex';
    try {
        const res = await fetch(`${API_BASE}/summarize`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ text })
        });
        if (!res.ok) {
            const errBody = await res.json().catch(() => null);
            const msg = errBody?.error?.message || 'Ошибка API';
            throw new Error(msg);
        }
        const data = await res.json();
        if (!data.success || !data.summaries || !data.summaries.length) {
            throw new Error('Пустой результат от API');
        }
        output.value = data.summaries[0].summary;
    } catch (err) {
        console.error('Ошибка суммаризации:', err);
        output.value = 'Ошибка: ' + err.message;
    } finally {
        const words = output.value.trim().split(/\s+/).filter(Boolean).length;
        const reviews = window.lastCsvCount || 1;
        document.getElementById('outputCount').textContent =
            'Слова: ' + words + (window.lastCsvCount ? ` | Отзывов: ${reviews}` : '');
        loading.style.display = 'none';
    }
}

function copyResult() {
    if (!output.value) return;
    navigator.clipboard.writeText(output.value);
    const btn = event.target;
    const originalText = btn.textContent;
    btn.textContent = 'Копирован!';
    setTimeout(() => btn.textContent = originalText, 2000);
}
function downloadResult() {
    if (!output.value) return;
    const blob = new Blob([output.value], { type: 'text/plain' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = 'summary.txt';
    a.click();
}

uploadBtn.addEventListener('click', () => {
    fileInput.click();
});

fileInput.addEventListener('change', function () {
    const file = this.files[0];
    if (!file) return;

    if (!file.name.toLowerCase().endsWith('.csv')) {
        alert('Пожалуйста, выберите файл CSV.');
        return;
    }

    try {
        Papa.parse(file, {
            header: true,
            skipEmptyLines: true,
            complete: (res) => {
                const rows = res.data || [];
                const texts = rows
                    .map(r => {
                        const content = r.Original_text || r.text || r.content || r.review || '';
                        if (!content) return '';
                        const id = r.ID || r.id || '';
                        return id ? `ID: ${id}\n${content}` : content;
                    })
                    .filter(Boolean);
                if (texts.length) {
                    input.value = texts.join('\n\n');
                    input.dispatchEvent(new Event('input'));
                    window.lastCsvCount = texts.length;
                }
            }
        });
    } catch (e) {
        console.error('Ошибка чтения CSV на фронтенде:', e);
    }
});