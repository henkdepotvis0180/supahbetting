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
echo [1/5] Hardware herkennen
%PYCMD% -m supahbetting.hardware_profile --cap 16
if errorlevel 1 goto fail
for /f "delims=" %%W in ('%PYCMD% -m supahbetting.hardware_profile --cap 16 --workers-only') do set "WORKERS=%%W"
if not defined WORKERS goto fail
echo CPU-processen voor training: %WORKERS%
echo [2/5] Regressietests
%PYCMD% -m unittest discover -s tests -v
if errorlevel 1 goto fail
echo [3/5] Snelle controle
%PYCMD% -m supahbetting.local_optimizer --quick --workers %WORKERS% --hours 0.1
if errorlevel 1 goto fail
echo [4/5] Uitgebreide optimalisatie (budget 4 uur)
%PYCMD% -m supahbetting.local_optimizer --workers %WORKERS% --hours 4
if errorlevel 1 goto fail
echo [5/5] Afgeronde resultaten automatisch naar GitHub
%PYCMD% -m supahbetting.github_training_sync
if errorlevel 1 goto uploadfail
echo.
echo Training gereed en resultaten geupload naar de experimentele GitHub-branch.
goto end
:uploadfail
echo.
echo Training lokaal klaar, maar GitHub-upload is niet gelukt.
echo Gebruik GitHub CLI: gh auth login
echo Daarna opnieuw uploaden zonder hertraining:
echo   %PYCMD% -m supahbetting.github_training_sync
goto end
:fail
echo.
echo Fout tijdens hardwarecontrole, tests of training. Geen upload uitgevoerd.
:end
pause
