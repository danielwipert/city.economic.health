import os
import json
import pandas as pd
from huggingface_hub import InferenceClient

# 1. CONFIG
HF_TOKEN = os.getenv("HF_TOKEN")
MODEL_ID = "Qwen/Qwen2.5-72B-Instruct"  # Qwen 2.5 72B instruct model on HF

if HF_TOKEN is None:
    raise RuntimeError("Please set HF_TOKEN environment variable to your Hugging Face token.")


# 2. LOAD DATA (Excel or JSON)
def load_city_report(path: str) -> pd.DataFrame:
    """
    Load a city economic report from Excel (.xlsx/.xls) or JSON (.json)
    and return a pandas DataFrame.
    """
    path_lower = path.lower()
    if path_lower.endswith(".xlsx") or path_lower.endswith(".xls"):
        df = pd.read_excel(path)
    elif path_lower.endswith(".json"):
        df = pd.read_json(path)
    else:
        raise ValueError("Only .xlsx, .xls and .json files are supported for now.")

    # Optional: limit rows/columns for a first quick test
    # (helps keep prompts small and cheap)
    if len(df) > 200:
        df = df.head(200)

    return df


# 3. BUILD PROMPT FOR FINANCIAL TIMES–STYLE ANALYSIS
def build_prompt_from_df(df: pd.DataFrame, city_name: str = "Unknown City") -> str:
    """
    Convert the DataFrame into a compact JSON structure and embed it into
    a carefully written prompt that asks for FT-style analysis.
    """

    # Convert to record-oriented JSON
    records = df.to_dict(orient="records")

    # To avoid insanely long prompts, you might:
    # - Sample a subset of columns
    # - Or aggregate first (e.g., latest month only)
    # For now, we'll just dump as-is, but keep indentation small.
    data_json = json.dumps(records, indent=2)

    prompt = f"""
You are a senior economics columnist at the Financial Times.

Your task:
Use the dataset below to write a clear, analytically rigorous economic summary
for **{city_name}**. The audience is financially literate but not technical.
Assume this is for a short column or briefing note.

Writing style:
- Tone: neutral, evidence-based, Financial Times style.
- Avoid hype, clichés, and sweeping claims not grounded in the data.
- Use plain English, but not simplistic.
- Only cite specific numbers when they matter for the argument.

Analytical goals:
- Identify 2–3 key signals about the city's economic health.
- Distinguish between short-term shifts and medium-term trends where possible.
- Focus on labour market, housing, business activity, and any obvious stress points or strengths.
- Explicitly call out any indicators that look unusually strong or weak.

Structure:
1. **Opening overview (2–3 sentences):** what kind of city this is economically, and the headline story in the latest data.
2. **Analysis (2–3 paragraphs):** each paragraph should have a clear angle
   (for example: labour market conditions; housing and construction; business activity, investment, or consumer demand).
3. **Closing (1–2 sentences):** what to watch next, and how the latest data shifts the outlook, if at all.

Now, here is the city dataset you should rely on, in JSON format:

```json
{data_json}
