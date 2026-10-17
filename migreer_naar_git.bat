@echo off
setlocal
cd /d "%~dp0"
echo ===========================================================
echo  SupahBetting v0.13 - eenmalig Git installeren/migreren
echo ===========================================================
where git >nul 2>&1
if errorlevel 1 (
 echo Installeer eerst Git voor Windows.
 pause
 exit /b 1
)
if exist ".git\" (
 echo Deze map gebruikt al Git. Gebruik update_supahbetting.bat.
 pause
 exit /b 1
)
set "OLD=%~1"
if not defined OLD (
  echo.
  echo Voor behoud van jouw voorspellingen en API-sleutels:
  echo Geef de VOLLEDIGE map op van je oude uitgepakte SupahBetting.
  echo Je mag dit leeg laten als je geen oude gegevens wilt overzetten.
  set /p "OLD=Oude programmamap (of Enter voor nieuwe installatie): "
)
set "OLD=%OLD:"=%"
set "TARGET=%~dp0..\SupahBetting-Research-v013"
if exist "%TARGET%" (
 echo Doelmap bestaat al; bestaande Git/gegevens worden nooit overschreven:
 echo %TARGET%
 pause
 exit /b 1
)
echo.
echo Sluit oude CMD-vensters en het oude dashboard voor migratie.
echo Code eenmalig ophalen uit GitHub...
git clone --single-branch --branch feature/research-v0.13-serious-dashboard "https://github.com/henkdepotvis0180/supahbetting.git" "%TARGET%"
if errorlevel 1 (
 echo Installatie mislukt. Je oude ZIP is ongewijzigd.
 pause
 exit /b 1
)
if defined OLD (
  if exist "%OLD%\.supahbetting\" (
    echo Instellingen en lokale paperbet database veilig overzetten...
    robocopy "%OLD%\.supahbetting" "%TARGET%\.supahbetting" /E /R:1 /W:1 >nul
  )
  if exist "%OLD%\data\research\" (
    echo Historische caches en originele voorspellingslogs meenemen...
    robocopy "%OLD%\data\research" "%TARGET%\data\research" /E /R:1 /W:1 /XD "%OLD%\data\research\verified" >nul
  )
)
echo.
echo Je instellingen en historische bestanden zijn niet verwijderd.
echo Gereed! Gebruik voortaan deze bestanden in:
echo %TARGET%
echo   start_supahbetting.bat
echo   update_supahbetting.bat
echo.
pause
