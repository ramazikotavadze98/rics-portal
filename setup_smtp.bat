@echo off
REM RICS Portal - Persistent SMTP Configuration
REM This batch file sets environment variables and starts the server

setlocal enabledelayedexpansion

echo =====================================
echo RICS Portal - Gmail SMTP Setup
echo =====================================
echo.
echo Before running this script, you need:
echo 1. A Gmail account
echo 2. Enable "Less Secure App Access" at: https://myaccount.google.com/security
echo.

set /p EMAIL="Enter your Gmail address (e.g., you@gmail.com): "
set /p PASSWORD="Enter your Gmail password: "

REM Set environment variables for SMTP
setx RICS_SMTP_HOST "smtp.gmail.com"
setx RICS_SMTP_PORT "587"
setx RICS_SMTP_USERNAME "%EMAIL%"
setx RICS_SMTP_PASSWORD "%PASSWORD%"
setx RICS_SMTP_FROM "%EMAIL%"

echo.
echo Environment variables configured!
echo.
echo ✓ RICS_SMTP_HOST = smtp.gmail.com
echo ✓ RICS_SMTP_PORT = 587
echo ✓ RICS_SMTP_USERNAME = %EMAIL%
echo ✓ RICS_SMTP_PASSWORD = (set)
echo ✓ RICS_SMTP_FROM = %EMAIL%
echo.
echo NOTE: You may need to restart your terminal/PowerShell for changes to take effect.
echo.
pause
