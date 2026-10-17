@echo off
cd /d "%~dp0"
echo SupahBetting - bronbestanden
where py >nul 2>&1
if errorlevel 1 (
    python -m supahbetting.research_cli scan
) else (
    py -3 -m supahbetting.research_cli scan
)
echo.
echo Kopieer je export naar de map voor de juiste fork:
echo .supahbetting\imports\prophitbet
echo .supahbetting\imports\oddsharvester
echo .supahbetting\imports\prediict
echo.
pause
