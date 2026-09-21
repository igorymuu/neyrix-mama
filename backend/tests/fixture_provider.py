"""Local test-only LLM fixture; never included in production service commands."""

from http.server import BaseHTTPRequestHandler, HTTPServer
import json


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        if body.get("response_format"):
            content = json.dumps(
                {
                    "title": "Общий анализ крови (тест)",
                    "date": "2026-09-18",
                    "confidence": 0.93,
                    "values": [
                        {
                            "kind": "lab",
                            "title": "Гемоглобин",
                            "value": 118,
                            "unit": "г/л",
                            "reference": "см. оригинал",
                            "confidence": 0.93,
                        }
                    ],
                },
                ensure_ascii=False,
            )
        else:
            content = "Тестовый ответ провайдера: подготовьте вопросы и результаты анализов к приёму. Это проверка интеграции, а не медицинская рекомендация."
        result = json.dumps({"choices": [{"message": {"content": content}}]}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(result)

    def log_message(self, *args):
        pass


if __name__ == "__main__":
    HTTPServer(("127.0.0.1", 9100), Handler).serve_forever()
