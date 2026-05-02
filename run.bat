@echo off
REM Launch the Bond Valuation Workbench on Windows.
cd /d "%~dp0"

if not exist ".venv" (
    echo Creating virtual environment .venv ...
    python -m venv .venv
)

call .venv\Scripts\activate.bat

echo Installing dependencies ...
python -m pip install --quiet --upgrade pip
python -m pip install --quiet -r requirements.txt

echo Launching Streamlit ...
streamlit run ui\app.py
