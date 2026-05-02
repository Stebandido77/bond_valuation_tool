#!/usr/bin/env bash
# Launch the Bond Valuation Workbench.
set -e
cd "$(dirname "$0")"
if [ ! -d ".venv" ]; then
    echo "→ Creating virtual environment (.venv) ..."
    python3 -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate
echo "→ Installing dependencies ..."
pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt
echo "→ Launching Streamlit ..."
streamlit run ui/app.py
