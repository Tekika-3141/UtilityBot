@echo off
setlocal

set "PROJECT_DIR=%~dp0"
set "PYTHON=C:\Users\sota6\AppData\Local\Programs\Python\Python313\python.exe"

if not exist "%PYTHON%" (
    echo Python 3.13が見つかりません:
    echo %PYTHON%
    pause
    exit /b 1
)

start "UtilityBot Web" powershell.exe -NoExit -ExecutionPolicy Bypass -Command ^
    "Set-Location -LiteralPath '%PROJECT_DIR%'; $env:PYTHONPATH='src'; & '%PYTHON%' -m alembic upgrade head; if ($LASTEXITCODE -ne 0) { Write-Host 'Database migration failed.' -ForegroundColor Red; exit $LASTEXITCODE }; & '%PYTHON%' run_web.py"

start "UtilityBot Bot" powershell.exe -NoExit -ExecutionPolicy Bypass -Command ^
    "Set-Location -LiteralPath '%PROJECT_DIR%'; $env:PYTHONPATH='src'; & '%PYTHON%' run_bot.py"

echo UtilityBotのWebとBotを起動しました。
echo Web: http://localhost:8000
endlocal
