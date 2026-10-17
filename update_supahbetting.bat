@echo off
setlocal
cd /d "%~dp0"
if not exist ".git\" (
 echo ZIP-map gevonden. Voer eerst migreer_naar_git.bat uit
 echo en geef jouw vorige SupahBetting-map op om data te behouden.
 pause
 exit /b 1
)
where git >nul 2>&1
if errorlevel 1 (
 echo Git voor Windows ontbreekt.
 pause
 exit /b 1
)
git diff --quiet
if errorlevel 1 (
 echo Niet-gecommitte codewijzigingen aanwezig. Geen update uitgevoerd.
 pause
 exit /b 1
)
git diff --cached --quiet
if errorlevel 1 (
 echo Nog te committen codewijzigingen. Update gestopt.
 pause
 exit /b 1
)
for /f "delims=" %%B in ('git branch --show-current') do set "BRANCH=%%B"
if /I not "%BRANCH%"=="feature/eredivisie-data-v0.14" (
 echo Deze map staat op branch %BRANCH%
 echo Gebruik de nieuwe v0.14-map via migreer_naar_git.bat
 echo om andere experimentele versies niet ongemerkt te mengen.
 pause
 exit /b 1
)
git pull --ff-only origin feature/eredivisie-data-v0.14
if errorlevel 1 (
 echo Code niet veilig bijgewerkt; lokale trainingsgegevens blijven behouden.
 pause
 exit /b 1
)
echo v0.14-code bijgewerkt. Je API-configuratie en lokale scores blijven intact.
call "%~dp0start_supahbetting.bat"
