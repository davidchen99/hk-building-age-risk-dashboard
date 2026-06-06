@echo off
setlocal

cd /d "%~dp0"

echo Starting HK Building Asset Age Risk Dashboard...
echo.
echo Open this URL in your browser:
echo http://localhost:8501
echo.

if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" -m streamlit run app.py --server.port 8501
) else (
    python -m streamlit run app.py --server.port 8501
)

pause
