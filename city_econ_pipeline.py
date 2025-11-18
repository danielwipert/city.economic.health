import os
import json
import re
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd
from huggingface_hub import InferenceClient


# --------------------------------------------------------
# CONFIG
# --------------------------------------------------------

HF_TOKEN = os.getenv("HF_TOKEN")
if HF_TOKEN is None:
    raise RuntimeError("HF_TOKEN not set. In PowerShell run:\n"
                       "$env:HF_TOKEN = 'hf_your_token_here'")

# Analysis model (econ reasoning)
ANALYSIS_MODEL_ID = "Qwen/Qwen2.5-72B-Instruct"

# Stylist model (prose polish, 8B for speed/cost)
STYLE_MODEL_ID = "meta-llama/Llama-3.1-8B-Instruct"

# Input JSON
JSON_PATH = "calculated_metrics_reconciled.json"

# City identifier inside metros[]
PRIMARY_CITY_COLUMN = "primary_city"   # will use if present
FALLBACK_CITY_COLUMN = "msa"           # fallback if primary_city missing

# Output directory
OUTPUT_DIR = Path("city_reports_ft")

# Parallelism (how many cities at once)
MAX_WORKERS = 4


# --------------------------------------------------------
# UTILS
# --------------------------------------------------------

def slugify(name: str) -> str:
    """Convert a city name into a safe filename."""
    name = name.strip().lower()
    name = re.sub(r"[^a-z0-9]+", "-", name)
    return name.strip("-") or "city"


# --------------------------------------------------------
# DATA LOADING
# --------------------------------------------------------

def load_metros(path: str) -> pd.DataFrame:
    """
    Load your JSON and extract the metros list into a DataFrame.

    Expected structures:
      - { ..., "metros": [ {...}, {...}, ... ] }
      - or [ { ..., "metros": [ ... ] }, ... ]
    """
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Case 1: top-level dict with 'metros'
    if isinstance(data, dict) and "metros" in data:
        return pd.DataFrame(data["metros"])

    # Case 2: list of dicts, one of which has 'metros'
    if isinstance(data, list):
        for entry in data:
            if isinstance(entry, dict) and "metros" in entry:
                return pd.DataFrame(entry["metros"])

    raise ValueError("Unable to find 'metros' list in JSON file.")


# --------------------------------------------------------
# PROMPT BUILDERS
# --------------------------------------------------------

def build_analysis_prompt(df_city: pd.DataFrame, city_name: str) -> str:
    """
    Build the prompt that Qwen will use to produce the economic analysis.
    """
    records = df_city.to_dict(orient="records")
    data_json = json.dumps(records, indent=2)

    prompt = (
        f"Write a concise, evidence-based economic analysis of {city_name}.\n\n"
        "Audience: financially literate professional readers.\n"
        "Tone: Financial Times — neutral, analytical, precise.\n\n"
        "Requirements:\n"
        "- Identify the main signals in the city's economic indicators.\n"
        "- Distinguish short-term versus longer-term trends where possible.\n"
        "- Discuss labour market, housing, business activity, and any obvious stress points or strengths.\n"
        "- Use specific numbers only when they materially shape the argument.\n"
        "- Produce 2–3 paragraphs and a short closing outlook.\n\n"
        "Dataset (JSON):\n"
        f"{data_json}"
    )
    return prompt


def build_polish_prompt(raw_text: str, city_name: str) -> str:
    """
    Build the prompt that Llama will use to polish the Qwen draft.
    """
    prompt = (
        f"You are an elite copy editor at the Financial Times.\n\n"
        f"Your task is to rewrite the following economic column about {city_name}.\n"
        "- Preserve all factual claims and numerical values.\n"
        "- Improve clarity, rhythm, and flow.\n"
        "- Tighten repetition and remove vague or redundant phrases.\n"
        "- Maintain a neutral, analytical FT tone.\n"
        "- Do NOT introduce new data or speculate beyond what is already present.\n\n"
        "Here is the draft column to edit:\n\n"
        f"{raw_text}"
    )
    return prompt


# --------------------------------------------------------
# MODEL CALLS
# --------------------------------------------------------

def call_qwen_analysis(prompt: str) -> str:
    """
    Call Qwen 2.5 72B Instruct to produce the economic analysis.
    """
    client = InferenceClient(model=ANALYSIS_MODEL_ID, token=HF_TOKEN)

    completion = client.chat_completion(
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a senior economics columnist at the Financial Times. "
                    "Write clear, neutral, data-driven economic analysis."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        max_tokens=800,
        temperature=0.3,
        top_p=0.9,
    )

    return completion.choices[0].message["content"]


def call_llama_polish(prompt: str) -> str:
    """
    Call Llama 3.1 8B Instruct to polish the Qwen draft.
    """
    client = InferenceClient(model=STYLE_MODEL_ID, token=HF_TOKEN)

    completion = client.chat_completion(
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a world-class copy editor for the Financial Times. "
                    "You refine wording and structure but do not invent new facts."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        max_tokens=600,
        temperature=0.2,  # low temp = controlled style
        top_p=0.9,
    )

    return completion.choices[0].message["content"]


# --------------------------------------------------------
# PER-CITY PIPELINE
# --------------------------------------------------------

def process_city(city: str, df: pd.DataFrame, city_col: str) -> Path:
    """
    Full pipeline for a single city:
      - subset data
      - Qwen analysis
      - Llama polish
      - write markdown file
    Returns the output file path.
    """
    df_city = df[df[city_col] == city]

    analysis_prompt = build_analysis_prompt(df_city, city)
    raw_analysis = call_qwen_analysis(analysis_prompt)

    polish_prompt = build_polish_prompt(raw_analysis, city)
    polished_analysis = call_llama_polish(polish_prompt)

    OUTPUT_DIR.mkdir(exist_ok=True)
    filename = OUTPUT_DIR / f"{slugify(city)}.md"

    with open(filename, "w", encoding="utf-8") as f:
        f.write(f"# {city} — Economic Overview (FT Style)\n\n")
        f.write("## Polished FT-style column\n\n")
        f.write(polished_analysis.strip())
        f.write("\n\n---\n\n")
        f.write("## Original Qwen draft (for reference)\n\n")
        f.write(raw_analysis.strip())
        f.write("\n")

    return filename


# --------------------------------------------------------
# MAIN
# --------------------------------------------------------

def main():
    print("Loading metros from JSON...")
    df_metros = load_metros(JSON_PATH)

    # Decide which column identifies the city
    if PRIMARY_CITY_COLUMN in df_metros.columns:
        city_col = PRIMARY_CITY_COLUMN
    elif FALLBACK_CITY_COLUMN in df_metros.columns:
        city_col = FALLBACK_CITY_COLUMN
    else:
        raise ValueError(
            f"Neither '{PRIMARY_CITY_COLUMN}' nor '{FALLBACK_CITY_COLUMN}' "
            f"found in metro columns: {list(df_metros.columns)}"
        )

    cities = sorted(df_metros[city_col].dropna().unique())
    print(f"Using city column: {city_col}")
    print(f"Found {len(cities)} cities.\n")

    OUTPUT_DIR.mkdir(exist_ok=True)

    # Parallel processing
    futures = {}
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        for city in cities:
            futures[executor.submit(process_city, city, df_metros, city_col)] = city

        for future in as_completed(futures):
            city = futures[future]
            try:
                path = future.result()
                print(f"[OK] {city} → {path}")
            except Exception as e:
                print(f"[ERROR] {city}: {e}")

    print("\nDone. All available city reports generated in:", OUTPUT_DIR.resolve())


if __name__ == "__main__":
    main()
