@echo off
setlocal
cd /d "%~dp0"
echo.
echo ================================================
echo  SupahBetting - basismodel opnieuw trainen
echo ================================================
echo.
set "SOURCE=%~dp0.supahbetting\training_history.csv"
set "ENV_DIR=%~dp0.supahbetting\training-venv"
set "PYTHON=%ENV_DIR%\Scripts\python.exe"
if not exist "%SOURCE%" (
    echo Bestand niet aanwezig:
    echo %SOURCE%
    echo.
    echo Plaats hier je VOLLEDIGE historische wedstrijdhistorie,
    echo inclusief de nieuwste uitslagen.
    echo Voor de eerste geschiedenis kun je de CSV in je
    echo Prediict-fork gebruiken en die later uitbreiden.
    echo.
    pause
    exit /b 1
)
if not exist "%PYTHON%" (
    where py >nul 2>&1
    if not errorlevel 1 (
        py -3 -m venv "%ENV_DIR%"
    ) else (
        python -m venv "%ENV_DIR%"
    )
    if errorlevel 1 (
        echo Kon geen Python trainingsomgeving aanmaken.
        pause
        exit /b 1
    )
)
echo Training-afhankelijkheden installeren of controleren...
"%PYTHON%" -m pip install --disable-pip-version-check -r requirements-training.txt
if errorlevel 1 (
    echo Kon scikit-learn of numpy niet installeren.
    pause
    exit /b 1
)
echo.
echo Nieuwe parameters trainen en historisch toetsen...
"%PYTHON%" -m supahbetting.train_baseline --input "%SOURCE%" --output "%~dp0models\baseline_v1.json"
if errorlevel 1 (
    echo Training niet gelukt. Het bestaande model is niet vervangen.
    pause
    exit /b 1
)
echo.
echo Training afgerond. Herstart start_dashboard.bat om
echo het nieuwe lokale JSON-model in te laden.
pause
