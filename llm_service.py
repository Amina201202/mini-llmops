import csv
import os
import time
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI, RateLimitError, APITimeoutError

# .env faylindaki deyerleri os.environ-a yukleyir
load_dotenv()

API_KEY = os.getenv("LLM_API_KEY")
BASE_URL = os.getenv("LLM_BASE_URL")  # gemini ucun openai-uygun endpoint
PRIMARY_MODEL = os.getenv("PRIMARY_MODEL", "gemini-3.5-flash")
FALLBACK_MODEL = os.getenv("FALLBACK_MODEL", "gemini-3.5-flash-lite")

MAX_ATTEMPTS = 3
ERROR_MESSAGE = "Bağışlayın, hazırda cavab verə bilmirəm. Bir az sonra yenidən cəhd edin."

# qiymetler 1 milyon token ucun, dollarla (ai.google.dev/gemini-api/docs/pricing)
PRICES = {
    "gemini-3.5-flash": {"input": 1.50, "output": 9.00},
    "gemini-3.5-flash-lite": {"input": 0.30, "output": 2.50},
}

# csv hemise layihe qovlugunda yaransin, terminal haradan acilsa da
COSTS_FILE = Path(__file__).parent / "costs.csv"

# eyni sual tekrar gelende llm-e getmesin deye cavablari burda saxlayiram
CACHE = {}

_client = None


def get_client():
    # client-i ilk lazim olanda yaradiram, import zamani yox
    # yoxsa CI-da acar olmayanda testler import-da partlayardi
    global _client
    if _client is None:
        _client = OpenAI(
            api_key=API_KEY,
            base_url=BASE_URL,
            timeout=15,      # 15 saniyeden cox gozlemesin
            max_retries=0,   # sdk ozu retry etmesin, retry-i ozumuz idare edirik
        )
    return _client


def real_llm_call(model, question):
    response = get_client().chat.completions.create(
        model=model,
        messages=[
            # 200 token az oldugu ucun qisa cavab isteyirem ki yarimciq qalmasin
            {"role": "system", "content": "Qısa cavab ver, maksimum 3-4 cümlə."},
            {"role": "user", "content": question},
        ],
        max_tokens=200,
        # gemini 3.5-de "minimal" dusunmeni sifira endirir, debug-da yoxladim
        reasoning_effort="minimal",
    )
    text = response.choices[0].message.content or ""
    usage = response.usage
    # dusunme tokenleri completion_tokens-de gorunmur amma output kimi pul tutulur
    # ona gore output-u umumi - input kimi hesablayiram
    output_tokens = usage.total_tokens - usage.prompt_tokens
    return text, usage.prompt_tokens, output_tokens


def calculate_cost(model, input_tokens, output_tokens):
    price = PRICES.get(model)
    # qiymeti bilmediyimiz model ucun 0 yaziram ki proqram dayanmasin
    if price is None:
        return 0.0
    cost = (input_tokens * price["input"] + output_tokens * price["output"]) / 1_000_000
    return round(cost, 8)


def log_cost(model, input_tokens, output_tokens):
    cost = calculate_cost(model, input_tokens, output_tokens)
    # fayl yoxdursa evvelce basliq setrini yaziram
    is_new = not COSTS_FILE.exists()
    with open(COSTS_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if is_new:
            writer.writerow(["tarix", "model", "input_tokens", "output_tokens", "cost_usd"])
        writer.writerow([
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            model,
            input_tokens,
            output_tokens,
            cost,
        ])


def call_with_retry(llm_call, model, question):
    for attempt in range(MAX_ATTEMPTS):
        try:
            return llm_call(model, question)
        except (RateLimitError, APITimeoutError):
            # son cehd idise artiq gozlemirem, xetani yuxari atiram
            if attempt == MAX_ATTEMPTS - 1:
                raise
            wait = 2 ** attempt  # 1 san, sonra 2 san - exponential backoff
            print(f"[{model}] müvəqqəti xəta, {wait} san gözləyirəm...")
            time.sleep(wait)


def ask(question: str, llm_call=None) -> str:
    # testde saxta funksiya oturmek ucun llm_call parametri var
    if llm_call is None:
        llm_call = real_llm_call

    # "Salam " ve "salam" eyni sual sayilsin deye bosluqlari silib kicik herfe salıram
    key = question.strip().lower()
    if key in CACHE:
        print("[cache] cavab yaddaşdan gəldi, LLM çağırılmadı")
        return CACHE[key]

    # evvel esas model, alinmasa ehtiyat model
    for model in (PRIMARY_MODEL, FALLBACK_MODEL):
        try:
            text, input_tokens, output_tokens = call_with_retry(llm_call, model, question)
            # yalniz ugurlu cagirisdan sonra xerci yaziram
            log_cost(model, input_tokens, output_tokens)
            # yalniz ugurlu cavabi cache-e qoyuram
            CACHE[key] = text
            return text
        except Exception as e:
            print(f"[{model}] uğursuz oldu: {type(e).__name__}: {e}")

    # xeta mesajini cache-e qoymuram, yoxsa sonra da hemise xeta qaytarardi
    return ERROR_MESSAGE


if __name__ == "__main__":
    print(ask("Python-da list və tuple arasındakı fərq nədir?"))
    print("---")
    # eyni sual ikinci defe - bu defe llm cagirilmamalidi
    print(ask("Python-da list və tuple arasındakı fərq nədir?"))