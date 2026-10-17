@echo off
setlocal
cd /d "%~dp0"
echo Eenmalige broncontrole, training en optionele GitHub-synchronisatie.
where py >nul 2>&1
if not errorlevel 1 (
  py -3 -m supahbetting.research_monitor --once
) else (
  python -m supahbetting.research_monitor --once
)
if errorlevel 1 (
  echo Onderzoeksrun niet volledig. Zie meldingen hierboven.
) else (
  echo Controle afgerond. Bekijk het onderzoeksdashboard.
)
pause
