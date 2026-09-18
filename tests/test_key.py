import os
from openai import OpenAI

api_key = "AQ.Ab8RN6K3tUVSvYVZaCAu9APXi6v_umegxCe-lfWe9JLGlZRsyA"
client = OpenAI(
    api_key=api_key,
    base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
)

models = ["gemini-2.5-flash", "gemini-3.6-flash", "gemini-3.1-pro-preview"]
for m in models:
    try:
        res = client.chat.completions.create(
            model=m,
            messages=[{"role": "user", "content": 'Respond with JSON: {"status": "ok"}'}],
            response_format={"type": "json_object"}
        )
        print(f"Model {m}: SUCCESS -> {res.choices[0].message.content}")
    except Exception as e:
        print(f"Model {m}: FAILED -> {e}")
