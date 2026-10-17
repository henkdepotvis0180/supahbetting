@echo off
setlocal
cd /d "%~dp0"
set "PYTHONUTF8=1"
echo ============================================================
echo   SupahBetting Research Monitor v0.12 (2016 - heden)
echo ============================================================
echo Controles ieder 6 uur. Gecontroleerde nieuwe uitslagen worden
echo lokaal verwerkt en automatisch geupload naar de testbranch.
echo Laat dit venster open. Ctrl+C stopt de monitor.
echo.
where py >nul 2>&1
if not errorlevel 1 (
  py -3 -m supahbetting.research_monitor --interval-hours 6
) else (
  where python >nul 2>&1
  if errorlevel 1 (
    echo Installeer eerst Python 3.11 of nieuwer.
    pause
    exit /b 1
  )
  python -m supahbetting.research_monitor --interval-hours 6
)
echo Monitor gestopt.
pause
