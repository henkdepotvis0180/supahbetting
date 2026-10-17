@echo off
setlocal
cd /d "%~dp0"
echo ====================================================
echo  SupahBetting v0.14 - eerste Git installatie
echo ====================================================
where git >nul 2>&1
if errorlevel 1 (
 echo Installeer eerst Git voor Windows.
 pause
 exit /b 1
)
if exist ".git\" (
 echo Deze map gebruikt al Git; gebruik update_supahbetting.bat.
 pause
 exit /b 1
)
set "OLD=%~1"
if not defined OLD (
 echo.
 echo Geef de VOLLEDIGE MAP van je vorige SupahBetting-installatie op.
 echo Daaruit bewaren we .supahbetting en data\research.
 echo Leeg laten kan alleen als je die gegevens niet nodig hebt.
 set /p "OLD=Oude programmamap (of Enter zonder migratie): "
)
set "OLD=%OLD:"=%"
set "TARGET=%~dp0..\SupahBetting-Eredivisie-v014"
if exist "%TARGET%" (
 echo De doelmap bestaat al: %TARGET%
 echo We overschrijven bewust GEEN bestaande bestanden.
 pause
 exit /b 1
)
echo Sluit vooraf oude server- en monitorvensters.
git clone --single-branch --branch feature/eredivisie-data-v0.14 "https://github.com/henkdepotvis0180/supahbetting.git" "%TARGET%"
if errorlevel 1 (
 echo Kon GitHub niet clonen. Oude bestanden zijn onaangeroerd.
 pause
 exit /b 1
)
if defined OLD (
  if exist "%OLD%\.supahbetting\" (
    echo Eerdere API-sleutels en database veilig kopieren...
    robocopy "%OLD%\.supahbetting" "%TARGET%\.supahbetting" /E /R:1 /W:1 >nul
  )
  if exist "%OLD%\data\research\" (
    echo Eerdere voorspellingen, controlelijsten en trainingsmodellen bewaren...
    robocopy "%OLD%\data\research" "%TARGET%\data\research" /E /R:1 /W:1 /XD "%OLD%\data\research\verified" >nul
  )
)
echo.
echo Migratie gereed. Oude programmamap is NIET verwijderd.
echo Nieuwe map: %TARGET%
echo Start daar start_supahbetting.bat en gebruik later
echo update_supahbetting.bat voor automatische code-updates.
pause
