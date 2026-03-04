@echo off
REM ====================================================================
REM NEXUS - Iniciar com duplo-clique
REM Este arquivo pode ser colocado na Área de Trabalho ou no
REM Startup do Windows (shell:startup) para inicialização automática.
REM ====================================================================

cd /d "%~dp0"
powershell.exe -ExecutionPolicy Bypass -File "%~dp0NEXUS_Service.ps1"
