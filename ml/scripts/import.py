"""
import.py — ETL pipeline for the Stack Overflow Developer Survey CSV.

Reads:  data/survey_results_public.csv  (relative to project root)
Writes: PostgreSQL  →  responses  table

Column mapping (CSV → DB):
  ResponseId              → respondent_id
  Country                 → country
  YearsCodePro            → years_code_pro
  DevType                 → dev_type          (semicolon-split → array)
  LanguageHaveWorkedWith  → languages_worked  (semicolon-split → array)
  LanguageWantToWorkWith  → languages_wanted  (semicolon-split → array)
  PlatformHaveWorkedWith  → devops_tools      (semicolon-split → array)
  ConvertedCompYearly     → converted_comp_yearly
  EdLevel                 → ed_level
  AIToolCurrently         → ai_tool_used      (bool)
  LearnCodeOnline         → learn_code_online (bool)
"""

import os
import sys
import csv
import time
import psycopg2
import psycopg2.extras
from pathlib import Path
from dotenv import load_dotenv

# ── Config ────────────────────────────────────────────────────────────────────
ROOT = Path(__file__).parent.parent.parent          # project root
load_dotenv(dotenv_path=ROOT / '.env')

DB_CONFIG = {
    'host':     os.getenv('DB_HOST', 'localhost'),
    'port':     os.getenv('DB_PORT', '5432'),
    'dbname':   os.getenv('DB_NAME', 'survey_db'),
    'user':     os.getenv('DB_USER', 'postgres'),
    'password': os.getenv('DB_PASSWORD', 'postgres'),
}

CSV_PATH = ROOT / os.getenv('CSV_PATH', 'data/survey_results_public.csv').lstrip('../')

BATCH_SIZE = 500          # rows per INSERT batch
COMP_MIN   = 1_000        # drop implausibly low salaries
COMP_MAX   = 5_000_000    # drop implausibly high salaries

# Stack Overflow CSV column names  →  DB column names
COL_MAP = {
    'ResponseId':              'respondent_id',
    'Country':                 'country',
    'YearsCodePro':            'years_code_pro',
    'DevType':                 'dev_type',
    'LanguageHaveWorkedWith':  'languages_worked',
    'LanguageWantToWorkWith':  'languages_wanted',
    'PlatformHaveWorkedWith':  'devops_tools',
    'ConvertedCompYearly':     'converted_comp_yearly',
    'EdLevel':                 'ed_level',
    'AIToolCurrently':         'ai_tool_used',
    'LearnCodeOnline':         'learn_code_online',
}

# Semicolon-delimited columns that become Postgres text[] arrays
ARRAY_COLS = {'dev_type', 'languages_worked', 'languages_wanted', 'devops_tools'}

# ── Helpers ───────────────────────────────────────────────────────────────────

def parse_int(val: str):
    """Return int or None; handles 'Less than 1 year' etc."""
    if not val or val.strip() in ('', 'NA', 'NaN'):
        return None
    val = val.strip().lower()
    if 'less than 1' in val:
        return 0
    if 'more than 50' in val or '50 or more' in val:
        return 50
    try:
        return int(float(val))
    except ValueError:
        return None


def parse_float(val: str):
    """Return float or None."""
    if not val or val.strip() in ('', 'NA', 'NaN'):
        return None
    try:
        f = float(val)
        return f if COMP_MIN <= f <= COMP_MAX else None
    except ValueError:
        return None


def parse_array(val: str):
    """Split semicolon-delimited string into a list, or return None."""
    if not val or val.strip() in ('', 'NA', 'NaN'):
        return None
    parts = [p.strip() for p in val.split(';') if p.strip()]
    return parts if parts else None


def parse_bool(val: str):
    """Treat any non-empty, non-NA value as True."""
    if not val or val.strip() in ('', 'NA', 'NaN', 'None', 'I don\'t use any AI tools'):
        return False
    return True


def transform_row(raw: dict) -> dict | None:
    """
    Map one CSV row → one DB row dict.
    Returns None to skip the row entirely.
    """
    row = {}

    # respondent_id
    rid = parse_int(raw.get('ResponseId', ''))
    if rid is None:
        return None
    row['respondent_id'] = rid

    # country
    row['country'] = raw.get('Country', '').strip() or None

    # years_code_pro
    row['years_code_pro'] = parse_int(raw.get('YearsCodePro', ''))

    # array columns
    row['dev_type']          = parse_array(raw.get('DevType', ''))
    row['languages_worked']  = parse_array(raw.get('LanguageHaveWorkedWith', ''))
    row['languages_wanted']  = parse_array(raw.get('LanguageWantToWorkWith', ''))
    row['devops_tools']      = parse_array(raw.get('PlatformHaveWorkedWith', ''))

    # salary — keep only plausible values
    row['converted_comp_yearly'] = parse_float(raw.get('ConvertedCompYearly', ''))

    # education
    row['ed_level'] = raw.get('EdLevel', '').strip() or None

    # booleans
    row['ai_tool_used']      = parse_bool(raw.get('AIToolCurrently', ''))
    row['learn_code_online'] = parse_bool(raw.get('LearnCodeOnline', ''))

    return row


# ── DB helpers ────────────────────────────────────────────────────────────────

INSERT_SQL = """
    INSERT INTO responses (
        respondent_id, country, years_code_pro,
        dev_type, languages_worked, languages_wanted, devops_tools,
        converted_comp_yearly, ed_level, ai_tool_used, learn_code_online
    )
    VALUES %s
    ON CONFLICT (respondent_id) DO UPDATE SET
        country                = EXCLUDED.country,
        years_code_pro         = EXCLUDED.years_code_pro,
        dev_type               = EXCLUDED.dev_type,
        languages_worked       = EXCLUDED.languages_worked,
        languages_wanted       = EXCLUDED.languages_wanted,
        devops_tools           = EXCLUDED.devops_tools,
        converted_comp_yearly  = EXCLUDED.converted_comp_yearly,
        ed_level               = EXCLUDED.ed_level,
        ai_tool_used           = EXCLUDED.ai_tool_used,
        learn_code_online      = EXCLUDED.learn_code_online,
        imported_at            = NOW()
"""

def row_to_tuple(r: dict) -> tuple:
    return (
        r['respondent_id'],
        r['country'],
        r['years_code_pro'],
        r['dev_type'],
        r['languages_worked'],
        r['languages_wanted'],
        r['devops_tools'],
        r['converted_comp_yearly'],
        r['ed_level'],
        r['ai_tool_used'],
        r['learn_code_online'],
    )


def flush_batch(cursor, batch: list[dict]):
    tuples = [row_to_tuple(r) for r in batch]
    psycopg2.extras.execute_values(cursor, INSERT_SQL, tuples, page_size=BATCH_SIZE)


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    # Validate CSV exists
    if not CSV_PATH.exists():
        print(f"❌ CSV not found at: {CSV_PATH}")
        print(f"   and place it at:  {CSV_PATH}")
        sys.exit(1)

    print(f"📂 CSV  : {CSV_PATH}")
    print(f"🗄️  DB   : {DB_CONFIG['dbname']}@{DB_CONFIG['host']}:{DB_CONFIG['port']}")
    print()

    # Connect
    print("⏳ Connecting to PostgreSQL...")
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        conn.autocommit = False
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        sys.exit(1)
    print("✅ Connected\n")

    # Stream CSV
    t0 = time.time()
    total_read = 0
    total_inserted = 0
    total_skipped  = 0
    batch: list[dict] = []

    with open(CSV_PATH, encoding='utf-8', newline='') as f:
        reader = csv.DictReader(f)

        # Warn about missing columns
        available = set(reader.fieldnames or [])
        expected  = set(COL_MAP.keys())
        missing   = expected - available
        if missing:
            print(f"⚠️  Missing CSV columns (will be NULL): {sorted(missing)}\n")

        with conn.cursor() as cur:
            for raw_row in reader:
                total_read += 1

                row = transform_row(raw_row)
                if row is None:
                    total_skipped += 1
                    continue

                batch.append(row)

                if len(batch) >= BATCH_SIZE:
                    flush_batch(cur, batch)
                    total_inserted += len(batch)
                    batch.clear()
                    elapsed = time.time() - t0
                    print(
                        f"  ↳ {total_inserted:>7,} inserted  |  "
                        f"{total_read:>7,} read  |  "
                        f"{elapsed:.1f}s",
                        end='\r'
                    )

            # Final partial batch
            if batch:
                flush_batch(cur, batch)
                total_inserted += len(batch)

            conn.commit()

    elapsed = time.time() - t0
    print(f"\n\n✅ Done in {elapsed:.1f}s")
    print(f"   Rows read     : {total_read:,}")
    print(f"   Rows imported : {total_inserted:,}")
    print(f"   Rows skipped  : {total_skipped:,}  (missing ResponseId)")
    print(f"\n👉 You can now run:  python ml/scripts/train.py")

    conn.close()


if __name__ == '__main__':
    main()
