@echo off
setlocal
cd /d "%~dp0"
set "DIR=%~dp0data\research\nl_csv_inbox"
if not exist "%DIR%" mkdir "%DIR%"
echo =========================================================
echo Eredivisie vanaf 2016 - handmatige historische CSV-import
echo =========================================================
echo Gebruik ALLEEN csv die je handmatig en rechtmatig hebt
echo gedownload. Automatisch scrapen wordt NIET gedaan.
echo Zet de N1 seizoenbestanden in de geopende map.
echo.
echo Bron: https://www.football-data.co.uk/netherlandsm.php
echo.
start "" explorer.exe "%DIR%"
echo Druk een toets nadat je de CSV-bestanden in de map hebt gezet.
pause >nul
where py >nul 2>&1
if not errorlevel 1 (
  py -3 -m supahbetting.research_nl_csv
) else (
  python -m supahbetting.research_nl_csv
)
echo.
echo Daarna start_supahbetting.bat draaien om resultaten te zien.
pause
