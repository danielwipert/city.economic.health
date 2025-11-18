import os
import json
import re
import pandas as pd
from pathlib import Path
from huggingface_hub import InferenceClient


# ---------------------------------
# CONFIG
# ---------------------------------
HF_TOKEN = os.getenv("HF_TOKEN")
MODEL_ID = "Qwen/Qwen2.5-72B-Instruct"
JSON_PATH = "calculated_metrics_reconciled.json"

# 👇 CHANGE THIS to whatever column in your JSON/DF identifies the city
CITY_COLUMN = "primary_city"   # e.g. "city", "MSA", "metro_name", etc.

# Where to save outputs
OUTPUT_DIR = Path("city_reports_ft")

if HF_TOKEN is None:
    raise RuntimeError(
        "HF_TOKEN environment variable not set. "
        "In PowerShell run: $env:HF_TOKEN = 'hf_abc123'"
    )


# ---------------------------------
# UTILS
# ---------------------------------
def slugify(name: str) -> str:
    """Turn a city name into a safe filename."""
    name = name.strip().lower()
    name = re.sub(r"[^a-z0-9]+", "-", name)
    return name.strip("-") or "city"


# ---------------------------------
# LOAD JSON
# ---------------------------------
def load_json_as_dataframe(path: str) -> pd.DataFrame:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if isinstance(data, dict):
        return pd.json_normalize(data)
    return pd.DataFrame(data)


# ---------------------------------
# BUILD PROMPT
# ---------------------------------
def build_prompt(df_city: pd.DataFrame, city_name: str) -> str:
    records = df_city.to_dict(orient="records")
    data_json = json.dumps(records, indent=2)

    prompt = (
        f"Write a concise, evidence-based economic analysis of {city_name}.\n\n"
        "Audience: financially literate, professional readers.\n"
        "Tone: Financial Times — neutral, analytical, precise.\n\n"
        "Requirements:\n"
        "- Identify key signals about the city's economic condition.\n"
        "- Distinguish short-term vs long-term trends.\n"
        "- Highlight labour market, housing, business activity, and inflation where possible.\n"
        "- Cite numbers ONLY when materially important.\n"
        "- Produce 2–3 paragraphs plus a short closing outlook.\n\n"
        "Dataset (JSON):\n"
        f"{data_json}"
    )

    return prompt


# ---------------------------------
# CALL QWEN — CHAT COMPLETION
# ---------------------------------
def call_qwen(prompt: str) -> str:
    client = InferenceClient(model=MODEL_ID, token=HF_TOKEN)

    completion = client.chat_completion(
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a senior economics columnist at the Financial Times. "
                    "Write clear, neutral, data-driven analysis."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        max_tokens=800,
        temperature=0.3,
        top_p=0.9,
    )

    return completion.choices[0].message["content"]


# ---------------------------------
# MAIN: LOOP OVER CITIES
# ---------------------------------
def analyze_all_cities():
    df = load_json_as_dataframe(JSON_PATH)

    if CITY_COLUMN not in df.columns:
        raise ValueError(
            f"CITY_COLUMN '{CITY_COLUMN}' not found in columns: {list(df.columns)}"
        )

    OUTPUT_DIR.mkdir(exist_ok=True)

    cities = sorted(df[CITY_COLUMN].dropna().unique())
    print(f"Found {len(cities)} cities in column '{CITY_COLUMN}'.\n")

    for city in cities:
        print(f"=== Processing {city} ===")
        df_city = df[df[CITY_COLUMN] == city]

        prompt = build_prompt(df_city, city)
        analysis = call_qwen(prompt)

        filename = OUTPUT_DIR / f"{slugify(city)}.md"
        with open(filename, "w", encoding="utf-8") as f:
            f.write(f"# {city} – Economic Overview (FT-style)\n\n")
            f.write(analysis)

        print(f"Saved report to {filename}\n")


if __name__ == "__main__":
    analyze_all_cities()
