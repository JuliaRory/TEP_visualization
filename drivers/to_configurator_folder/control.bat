@echo off
call env
cd /d "%~dp0"
set PATH=%CD%\bin;%PATH%
cd bin
start quickStimulus --load "C:\Users\hodor\Documents\lab-MSU\Works\2025.10_TMS\TEP_visualization\drivers\control.qml" --serviceConfig ..\params\resonance_control_params.json %*