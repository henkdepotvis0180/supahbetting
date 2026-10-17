@echo off
setlocal
cd /d "%~dp0"
set "PYTHONUTF8=1"
set "OMP_NUM_THREADS=1"
set "OPENBLAS_NUM_THREADS=1"
set "MKL_NUM_THREADS=1"
where py >nul 2>&1
if not errorlevel 1 (
  set "PYCMD=py -3"
) else (
  where python >nul 2>&1
  if errorlevel 1 (
    echo Python 3.11+ ontbreekt. Installeer Python vanaf https://www.python.org/downloads/
    pause
    exit /b 1
  )
  set "PYCMD=python"
)
echo [1/4] Hardware herkennen
%PYCMD% -m supahbetting.hardware_profile --cap 16
if errorlevel 1 goto fail
for /f "delims=" %%W in ('%PYCMD% -m supahbetting.hardware_profile --cap 16 --workers-only') do set "WORKERS=%%W"
if not defined WORKERS goto fail
echo CPU-processen voor training: %WORKERS%
echo [2/4] Regressietests
%PYCMD% -m unittest discover -s tests -v
if errorlevel 1 goto fail
echo [3/4] Snelle controle
%PYCMD% -m supahbetting.local_optimizer --quick --workers %WORKERS% --hours 0.1
if errorlevel 1 goto fail
echo [4/4] Uitgebreide optimalisatie (budget 4 uur)
%PYCMD% -m supahbetting.local_optimizer --workers %WORKERS% --hours 4
if errorlevel 1 goto fail
echo Gereed: training_reports\local_optimizer_report.json
goto end
:fail
echo Fout tijdens hardwarecontrole, tests of training.
:end
pause
