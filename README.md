# Mini LLMOps Servisi

Gemini API üzərində qurulmuş kiçik LLM servisi: timeout, retry (exponential backoff), fallback model, xərc qeydiyyatı, dict cache, pytest testləri və GitHub Actions CI.

## Quraşdırma

```bash
pip install -r requirements.txt
cp .env.example .env   # sonra .env-ə öz API açarını yaz
python run_questions.py
pytest -v
```

## Nəticələr

`ask` funksiyası 5 sualla işə salındı, onlardan biri (Python-da list və tuple fərqi) təkrar idi. LLM cəmi 4 dəfə çağırıldı və `costs.csv`-yə görə ümumi xərc **$0.0057** oldu (gemini-3.5-flash). Təkrar sual cache-dən qaytarıldı, beləliklə cache **1 sorğuya** qənaət etdi: bu, təxminən $0.0014, yəni ümumi xərcin ~20%-i qədərdir. Real sistemdə eyni suallar tez-tez təkrarlandığı üçün cache-in qənaəti daha böyük olardı.