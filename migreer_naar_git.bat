@echo off
setlocal
cd /d "%~dp0"
where git >nul 2>&1
if errorlevel 1 (
 echo Installeer eerst Git voor Windows of GitHub CLI met Git.
 pause
 exit /b 1
)
if exist ".git\" (
 echo Deze map gebruikt al Git; gebruik update_supahbetting.bat.
 pause
 exit /b 1
)
set "TARGET=%~dp0..\SupahBetting-Research-v013"
if exist "%TARGET%" (
 echo Doelmap bestaat al: %TARGET%
 echo Er wordt bewust niets overschreven.
 pause
 exit /b 1
)
echo Sluit je oude SupahBetting server en monitor voordat je verdergaat.
echo Nieuwe repository installeren in %TARGET%
git clone --branch feature/research-v0.13-serious-dashboard --single-branch "https://github.com/henkdepotvis0180/supahbetting.git" "%TARGET%"
if errorlevel 1 (
 echo GitHub clone mislukt. Oude ZIP-map is ongewijzigd.
 pause
 exit /b 1
)
if exist ".supahbetting\" (
 echo Persoonlijke configuratie en paperbetdatabase bewaren...
 robocopy ".supahbetting" "%TARGET%\.supahbetting" /E /R:1 /W:1 >nul
)
if exist "data\research\" (
 echo Eigen historische training en oorspronkelijke forecasttimestamps bewaren...
 robocopy "data\research" "%TARGET%\data\research" /E /R:1 /W:1 >nul
)
echo Installatie klaar! Oude bestanden blijven op hun originele plek.
echo Gebruik voortaan in %TARGET%:
echo   start_supahbetting.bat
echo   update_supahbetting.bat
pause
