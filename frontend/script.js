// =======================
// Lấy các element cơ bản
const input = document.getElementById('inputText');
const output = document.getElementById('outputText');
const uploadBox = document.getElementById('uploadBox');
const loading = document.getElementById('loading');
const clearBtn = document.getElementById('clearBtn');

// =======================
// Chọn độ dài summary
function updateLengthCheck() {
    const select = document.getElementById('length');
    const labels = { short: 'Короткий', medium: 'Средний', long: 'Длинный' };
    for (let option of select.options) {
        const text = labels[option.value];
        option.textContent = (option.selected ? '✔ ' : '') + text;
    }
    select.classList.add('highlight');
}
window.addEventListener('DOMContentLoaded', updateLengthCheck);

// =======================
// Input text thay đổi
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

// =======================
// Chuyển tab text/file
function switchTab(tab) {
    const tabText = document.getElementById('tabText');
    const tabFile = document.getElementById('tabFile');
    tabText.classList.remove('active');
    tabFile.classList.remove('active');
    if (tab === 'text') {
        tabText.classList.add('active');
        input.classList.remove('hidden');
        uploadBox.classList.add('hidden');
        if (input.value.length > 0) clearBtn.classList.remove('hidden');
    } else if (tab === 'file') {
        tabFile.classList.add('active');
        input.classList.add('hidden');
        uploadBox.classList.remove('hidden');
        clearBtn.classList.add('hidden');
    }
}

// =======================
// Xử lý file CSV local
document.getElementById('fileInput').addEventListener('change', function() {
    const file = this.files[0];
    if (!file) return;
    loading.style.display = 'flex';
    if (file.name.endsWith(".csv")) {
        Papa.parse(file, {
            header: true,
            skipEmptyLines: true,
            complete: function(results) {
                window.csvData = results.data.map(row => ({
                    product: row['Product'],
                    id: row['ID'],
                    content: row['Original_text']
                }));
                input.value = window.csvData.map(r => r.content).join("\n\n");
                switchTab('text');
                input.dispatchEvent(new Event('input'));
                loading.style.display = 'none';
            },
            error: function(err) {
                alert("Ошибка чтения CSV: " + err.message);
                loading.style.display = 'none';
            }
        });
    } else {
        alert("Пожалуйста, выберите файл CSV.");
        loading.style.display = 'none';
    }
});

// =======================
// MOCK CSV DỮ LIỆU
const mockCSVData = [
    { Product: "Влажный корм для собак PET PRIDE ", ID: "1", Original_text: "Корм хороший наверное, не пробовала, но собака ест с такой жадностью, что даже боюсь подходить. На упаковке не нашла даты изготовления продукции или срока годности. И ягнёнка там всего 4% судя по составу, указанному на упаковке, хотя заявлено что корм с содержанием мяса ягнёнка." },
    { Product: "Влажный корм для собак PET PRIDE ", ID: "2", Original_text: "Не травите своих собак этими консервами! Дала на пробу 1 ложку через час аллергическая реакция и понос. У многих так же, потом уже прочитала отзывы покупателей за последнее время. Может партия из испорченного сырья или подделка Штрих-код и кюар-код не считываются. Добиться объяснений не удалось, ссылаются на оригинал и сертификаты. Но какой в них толк, если собаки травятся(( Возврат не делают, в итоге почти тысяча в помойку + расходы на пробиотики, чтобы нормализовать стул собаке" },
    { Product: "Влажный корм для собак PET PRIDE ", ID: "3", Original_text: "Корм хороший, а вот с доставкой проблемы . Заказала корм трех видов в количестве 6, 12 и 12 штук. В день доставки привезли только 12 банок одного корма, а заказ получил статус «получен». При этом заказ был полностью оплачен! Пришлось писать в поддержку озон (у них ответ : писать продавцу) и продавцу, кое-как доставили еще 6 банок корма, а 12 оставшиеся не привезли. И снова заказ имеет статус «получен». И снова нужно писать продавцу! Продавец пока не ответил. Честно, в следующий раз подумаю, заказывать ли этот корм на озоне, да еще с полной предоплатой . Жду либо доставку, либо возврат средств. Спасибо" }
];
async function fetchMockCSV() {
    return new Promise(resolve => setTimeout(() => resolve(mockCSVData), 1000));
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
            switchTab('text');
            input.dispatchEvent(new Event('input'));
        })
        .catch(err => alert("Ошибка fetch: " + err.message))
        .finally(() => loading.style.display = 'none');
}

// =======================
// Nút thử mock CSV
document.getElementById('mockBtn').addEventListener('click', async () => {
    loading.style.display = 'flex';
    try {
        const data = await fetchMockCSV();
        window.csvData = data.map(row => ({
            product: row.Product,
            id: row.ID,
            content: row.Original_text
        }));
        input.value = window.csvData.map(r => r.content).join("\n\n");
        switchTab('text');
        input.dispatchEvent(new Event('input'));
    } catch (err) {
        alert("Ошибка mock: " + err.message);
    } finally {
        loading.style.display = 'none';
    }
});

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
