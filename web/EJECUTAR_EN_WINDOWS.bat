@echo off
title AeroTwin IQ Adaptive
if not exist .venv (
  echo Creando entorno virtual...
  python -m venv .venv
)
call .venv\Scripts\activate
echo Instalando dependencias...
python -m pip install -r requirements.txt
echo Iniciando AeroTwin IQ Adaptive...
python -m streamlit run app.py
pause
