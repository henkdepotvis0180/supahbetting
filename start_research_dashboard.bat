@echo off
setlocal
cd /d "%~dp0"
echo Start onderzoeksmonitor in een apart venster.
start "SupahBetting research data monitor" cmd /k ""%~dp0start_research_monitor.bat""
echo Start vervolgens het bestaande dashboard.
call "%~dp0start_dashboard.bat"
