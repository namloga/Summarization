// =======================
// Lấy các element cơ bản
const input = document.getElementById('inputText');
const output = document.getElementById('outputText');
const loading = document.getElementById('loading');
const clearBtn = document.getElementById('clearBtn');

// =======================
// Input text thay đổi
input.addEventListener('input', () => {
    window.csvData = null;

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

// =======================
// Fetch CSV từ server
function fetchCSVFromServer(url) {
    loading.style.display = 'flex';
    fetch(url)
        .then(res => {
            if (!res.ok) throw new Error("Ошибка сети");
            return res.json(); // server trả JSON dạng [{Product,ID,Original_text},...]
        })
        .then(data => {
            window.csvData = data.map(row => ({
                product: row.Product,
                id: row.ID,
                content: row.Original_text
            }));
            input.value = window.csvData.map(r => r.content).join("\n\n");
            input.dispatchEvent(new Event('input'));
        })
        .catch(err => alert("Ошибка fetch: " + err.message))
        .finally(() => loading.style.display = 'none');
}

// =======================
// Xử lý & xuất output
function startProcessing() {
    loading.style.display = 'flex';
    setTimeout(() => {
        if (window.csvData && window.csvData.length > 0) {
            // Xử lý file CSV
            const summarized = window.csvData.map(row => {
                const shortContent = row.content.slice(0, 150);
                return `Product: ${row.product}\nID: ${row.id}\nFeedback: ${shortContent}\n`;
            }).join("\n---\n");
            output.value = summarized;
        } else {
            // Xử lý text bình thường
            output.value = input.value.slice(0, 150);
        }
        document.getElementById('outputCount').textContent =
            'Слова: ' + output.value.trim().split(/\s+/).filter(Boolean).length;
        loading.style.display = 'none';
    }, 1500);
}

// =======================
// Copy / Download kết quả
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

const uploadBtn = document.getElementById('uploadBtn');
const fileInput = document.getElementById('fileInput');

uploadBtn.addEventListener('click', () => {
    fileInput.click();
});

fileInput.addEventListener('change', async function () {
    const file = this.files[0];
    if (!file) return;

    loading.style.display = 'flex';

    const formData = new FormData();
    formData.append("file", file);

    try {
        await new Promise(resolve => setTimeout(resolve, 1000));

        const data = {
            summary: "Тест API прошёл успешно."
        };

        output.value = data.summary;

        document.getElementById('outputCount').textContent =
            'Слова: ' + output.value.trim().split(/\s+/).filter(Boolean).length;

    } catch (err) {
        alert("Ошибка: " + err.message);
    } finally {
        loading.style.display = 'none';
    }
});