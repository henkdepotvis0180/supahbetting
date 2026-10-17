@echo off
setlocal
cd /d "%~dp0"
set "PYTHONUTF8=1"
set "OMP_NUM_THREADS=1"
set "OPENBLAS_NUM_THREADS=1"
set "MKL_NUM_THREADS=1"
echo SupahBetting v0.11 experimentele CPU-training
echo Productiemodel blijft ongewijzigd.
where py >nul 2>&1
if not errorlevel 1 (
  set "PYCMD=py -3"
) else (
  set "PYCMD=python"
)
echo [1/3] Snelle regressiecontrole
%PYCMD% -m unittest discover -s tests -v
if errorlevel 1 goto fail
echo [2/3] Snelle rooktest op historische wedstrijden
%PYCMD% -m supahbetting.local_optimizer --quick --workers 4 --hours 0.1
if errorlevel 1 goto fail
echo [3/3] Uitgebreide optimalisatie: maximaal 4 uur, 16 workers
%PYCMD% -m supahbetting.local_optimizer --workers 16 --hours 4
if errorlevel 1 goto fail
echo.
echo Gereed. Zie training_reports\local_optimizer_report.json
goto end
:fail
echo.
echo Training of tests mislukt; controleer de fout hierboven.
:end
pause
