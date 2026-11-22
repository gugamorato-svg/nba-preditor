@echo off
rem Captura em papel (so leitura de dados publicos). Feito para o Agendador de Tarefas do Windows.
rem Usa o Python da variavel NBA_PYTHON se existir; senao, o "python" do PATH.
chcp 65001 >nul
cd /d "%~dp0"
if not exist "data\cache" mkdir "data\cache"
set "PY=python"
if defined NBA_PYTHON set "PY=%NBA_PYTHON%"
echo ==== %date% %time% >> "data\cache\paper_collect.log"
"%PY%" paper_collect.py >> "data\cache\paper_collect.log" 2>&1
