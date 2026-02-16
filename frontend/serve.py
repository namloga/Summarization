"""
Запуск статического сервера для фронтенда.
Открыть в браузере: http://localhost:5500
"""
import http.server
import socketserver
import webbrowser
import os

PORT = 5500
DIR = os.path.dirname(os.path.abspath(__file__))

os.chdir(DIR)
Handler = http.server.SimpleHTTPRequestHandler
with socketserver.TCPServer(("", PORT), Handler) as httpd:
    print(f"Фронтенд: http://localhost:{PORT}")
    print("Убедитесь, что backend запущен: python -m src.main (в папке backend)")
    webbrowser.open(f"http://localhost:{PORT}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nОстановлено.")
