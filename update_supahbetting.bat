@echo off
setlocal
cd /d "%~dp0"
if not exist ".git\" (
 echo De huidige map is een ZIP-installatie, geen Git-checkout.
 echo Gebruik eenmalig migreer_naar_git.bat om de originele
 echo .supahbetting instellingen en data\research te bewaren.
 pause
 exit /b 1
)
where git >nul 2>&1
if errorlevel 1 (
 echo Git is niet geinstalleerd of ontbreekt in PATH.
 pause
 exit /b 1
)
echo Lokale veranderingen controleren...
git diff --quiet
if errorlevel 1 (
 echo De repository bevat gewijzigde bestanden. Bijwerken afgebroken.
 pause
 exit /b 1
)
git diff --cached --quiet
if errorlevel 1 (
 echo Er staan niet-gecommitte wijzigingen klaar. Bijwerken afgebroken.
 pause
 exit /b 1
)
echo Onderzoeksbranch bijwerken zonder bestaande data te verwijderen...
git pull --ff-only origin feature/research-v0.13-serious-dashboard
if errorlevel 1 (
 echo Git kon niet veilig bijwerken. Je lokale data zijn ongewijzigd.
 pause
 exit /b 1
)
echo Code bijgewerkt. De onderzoeksmodelgegevens blijven lokaal.
call "%~dp0start_supahbetting.bat"
