@echo off
setlocal
cd /d "%~dp0"
echo Vergelijk onafhankelijke Poisson en Dixon-Coles op echte historische resultaten.
echo Dit verandert geen actief model.
where py >nul 2>&1
if not errorlevel 1 (
  py -3 -m supahbetting.research_challengers
) else (
  python -m supahbetting.research_challengers
)
pause
