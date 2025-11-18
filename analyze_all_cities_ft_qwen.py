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

# These are columns INSIDE metros[]
CITY_COLUMN = "primary_city"       # can switch to "msa"
ALT_CITY_COLUMN = "msa"            # fallback if primary_city missing

# Save folder
OUTPUT_DIR = Path("city_reports_ft")

if HF_TOKEN is None:
    raise RuntimeError("HF_TOKEN not set. Use:  $env:HF_TOKEN = 'hf_xxx'")


# ---------------------------------
# HELPERS
# ---------------------------------
def slugify(name: str) -> str:
    name = name.strip().lower()
    name = re.sub(r"[^a-z0-9]+", "-", name)
    return name.strip("-") or "city"


# ---------------------------------
# LOAD JSON — SPECIAL FORMAT
# ---------------------------------
def load_metros(path: str) -> pd.DataFrame:
    """
    Your file contains a top-level 'metros' list inside a dict.
    Extract it and convert it to a DataFrame.
    """
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Case 1: top-level dict with key 'metros'
    if "metros" in data:
        return pd.DataFrame(data["metros"])

    # Case 2: list of dicts, each containing 'metros'
    if isinstance(data, list):
        for entry in data:
            if "metros" in entry:
                return pd.DataFrame(entry["metros"])

    raise ValueError("Unable to find 'metros' list in JSON file.")


# ---------------------------------
# PROMPT BUILDER
# ---------------------------------
def build_prompt(df_city: pd.DataFrame, city_name: str) -> str:
    records = df_city.to_dict(orient="records")
    data_json = json.dumps(records, indent=2)

    prompt = (
        f"Write a concise, evidence-based economic analysis of {city_name}.\n\n"
        "Audience: financially literate professionals.\n"
        "Tone: Financial Times — analytical, neutral, data-focused.\n\n"
        "Requirements:\n"
        "- Identify the main signals in the city's economic indicators.\n"
        "- Highlight short-term vs long-term patterns.\n"
        "- Discuss labour market, housing, business activity, and any anomalies.\n"
        "- Use numbers **only** when needed.\n"
        "- Produce 2–3 paragraphs and a short closing outlook.\n\n"
        "Dataset:\n"
        f"{data_json}"
    )
    return prompt


# ---------------------------------
# QWEN CALL
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
                )
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        max_tokens=800,
        temperature=0.3,
        top_p=0.9,
    )

    return completion.choices[0].message["content"]


# ---------------------------------
# MAIN LOOP — RUN FOR EACH CITY
# ---------------------------------
def analyze_all_cities():
    OUTPUT_DIR.mkdir(exist_ok=True)

    df = load_metros(JSON_PATH)

    # Choose a city identifier column
    city_col = CITY_COLUMN if CITY_COLUMN in df.columns else ALT_CITY_COLUMN

    print(f"Using city column: {city_col}\n")

    cities = sorted(df[city_col].dropna().unique())
    print(f"Found {len(cities)} cities.\n")

    for city in cities:
        print(f"=== Processing {city} ===")

        df_city = df[df[city_col] == city]

        prompt = build_prompt(df_city, city)
        analysis = call_qwen(prompt)

        filename = OUTPUT_DIR / f"{slugify(city)}.md"
        with open(filename, "w", encoding="utf-8") as f:
            f.write(f"# {city} — Economic Overview (FT Style)\n\n")
            f.write(analysis)

        print(f"Saved to {filename}\n")


if __name__ == "__main__":
    analyze_all_cities()
