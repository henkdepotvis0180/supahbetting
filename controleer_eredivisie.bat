@echo off
setlocal
cd /d "%~dp0"
echo =================================================
echo Eredivisie uitslagen controleren en lokaal trainen
echo =================================================
echo Haalt maximaal een heel DED seizoen op via je
echo lokaal ingestelde football-data.org API-toegang.
echo Geen API-sleutel? Het programma meldt dat netjes.
echo.
where py >nul 2>&1
if not errorlevel 1 (
  py -3 -m supahbetting.research_nl_api
) else (
  python -m supahbetting.research_nl_api
)
echo.
echo Gebruik 'ververs_speelschema.bat' om ook de kaartjes
echo met actuele kansen op de website te vernieuwen.
pause
