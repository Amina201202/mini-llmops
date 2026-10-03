from llm_service import ask

# 5 sual, 5-cisi 1-cinin tekrari - cache-i yoxlamaq ucun
questions = [
    "Python-da list və tuple arasındakı fərq nədir?",
    "REST API nədir?",
    "Docker konteyneri ilə virtual maşın arasındakı fərq nədir?",
    "Exponential backoff nə üçün istifadə olunur?",
    "Python-da list və tuple arasındakı fərq nədir?",
]

for i, q in enumerate(questions, start=1):
    print(f"\n=== Sual {i}: {q}")
    print(ask(q))