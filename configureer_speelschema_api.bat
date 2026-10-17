@echo off
setlocal
cd /d "%~dp0"
echo ===============================================
echo  SupahBetting - football-data.org API instellen
echo ===============================================
echo.
echo Dit is optioneel. Zonder token worden de beperkte
echo gratis speelschema's van TheSportsDB gebruikt.
echo.
echo Vul in het lokale instellingenbestand de
echo providers ^> football-data ^> api_key in.
echo Geen GitHub-token of bookmaker-token invullen.
echo.
where py >nul 2>&1
if not errorlevel 1 (
  py -3 -m supahbetting.provider_config --edit
) else (
  python -m supahbetting.provider_config --edit
)
pause
