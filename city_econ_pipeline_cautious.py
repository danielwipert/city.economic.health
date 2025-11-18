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
    raise RuntimeError(
        "HF_TOKEN not set. In PowerShell run:\n"
        "$env:HF_TOKEN = 'hf_your_token_here'"
    )

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
OUTPUT_DIR = Path("city_reports_ft_cautious")

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
    Build the prompt that Qwen will use to produce the economic analysis,
    with a cautious, descriptive FT tone.
    """
    records = df_city.to_dict(orient="records")
    data_json = json.dumps(records, indent=2)

    prompt = (
        f"Write a strict, evidence-based economic analysis of {city_name}.\n\n"
        "Tone: cautious, neutral, understated—classic Financial Times restraint.\n"
        "The goal is to describe patterns and signals without speculating about causes.\n\n"
        "Rules:\n"
        "- Do NOT infer causality unless it is directly and unambiguously supported by the data.\n"
        "- Avoid strong or dramatic adjectives (e.g., 'surging', 'collapsing', 'booming').\n"
        "- Avoid confident predictions about the future.\n"
        "- Use measured language such as 'suggests', 'indicates', 'may reflect', 'appears to'.\n"
        "- Do NOT add new facts, external context, or assumptions beyond what is implied by the data.\n"
        "- Focus on describing changes, contrasts, and notable levels in the indicators.\n"
        "- Aim for 2–3 concise, cautious paragraphs and a short, neutral closing sentence.\n\n"
        "Dataset (JSON):\n"
        f"{data_json}"
    )
    return prompt


def build_polish_prompt(raw_text: str, city_name: str) -> str:
    """
    Build the prompt that Llama will use to polish the Qwen draft,
    making it even more cautious and tight.
    """
    prompt = (
        f"You are a senior copy editor at the Financial Times.\n\n"
        f"Your task is to rewrite the following column about {city_name} in a "
        "cautious, measured, and restrained FT tone.\n\n"
        "Rules:\n"
        "- Preserve ALL facts, numerical values, and relationships exactly.\n"
        "- Do NOT introduce new interpretations, mechanisms, or causal claims.\n"
        "- Do NOT strengthen any conclusions beyond what the draft already states.\n"
        "- Prefer understatement over emphasis; avoid dramatic or high-intensity language.\n"
        "- Remove vague, speculative, or overly confident phrasing.\n"
        "- Keep sentences clear, compact, and analytical.\n"
        "- Maintain a neutral, descriptive voice focused on what the data shows.\n\n"
        "Rewrite the following text accordingly, keeping roughly the same length:\n\n"
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
                    "You are highly cautious and avoid speculation. You describe "
                    "what the data shows in neutral, measured language."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        max_tokens=800,
        temperature=0.25,  # lower for more consistent, less creative output
        top_p=0.9,
    )

    return completion.choices[0].message["content"]


def call_llama_polish(prompt: str) -> str:
    """
    Call Llama 3.1 8B Instruct to polish the Qwen draft with a cautious tone.
    """
    client = InferenceClient(model=STYLE_MODEL_ID, token=HF_TOKEN)

    completion = client.chat_completion(
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a Financial Times copy editor. You never add new facts "
                    "or interpretations. You only tighten wording, improve clarity, "
                    "and enforce a cautious, understated tone."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        max_tokens=600,
        temperature=0.15,  # very low for tight, controlled edits
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
        f.write(f"# {city} — Economic Overview (Cautious FT Style)\n\n")
        f.write("## Polished, cautious FT-style column\n\n")
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

    print("\nDone. All cautious city reports generated in:", OUTPUT_DIR.resolve())


if __name__ == "__main__":
    main()
