@echo off
setlocal
cd /d "%~dp0"
echo.
echo ============================================
echo  SupahBetting - lokale API-sleutels instellen
echo ============================================
echo.
where py >nul 2>&1
if not errorlevel 1 (
    py -3 -m supahbetting.provider_config --edit
) else (
    python -m supahbetting.provider_config --edit
)
if errorlevel 1 (
    echo.
    echo Fout: controleer of Python 3.11 of nieuwer is geinstalleerd.
)
echo.
pause
