@echo off
setlocal
cd /d "%~dp0"
set "PYTHONUTF8=1"
echo ================================================
echo  SupahBetting - Actuele wedstrijden en kansen
echo ================================================
echo Haalt een beperkt actueel speelschema op en maakt
echo experimentele 1X2-kansen per herkende wedstrijd.
echo Afspraken en API-limieten worden gerespecteerd.
echo.
where py >nul 2>&1
if not errorlevel 1 (
  py -3 -m supahbetting.research_upcoming
) else (
  where python >nul 2>&1
  if errorlevel 1 (
    echo Python 3.11+ ontbreekt.
    pause
    exit /b 1
  )
  python -m supahbetting.research_upcoming
)
if errorlevel 1 (
  echo Speelschema ophalen mislukt; controleer de fout hierboven.
) else (
  echo Gereed! Vernieuw in het dashboard bij
  echo "Wedstrijden vandaag en binnenkort".
)
pause
