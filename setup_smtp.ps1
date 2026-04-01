# RICS Portal SMTP Configuration Setup
# Run this script to configure Gmail SMTP for password reset emails

Write-Host "=====================================" -ForegroundColor Cyan
Write-Host "RICS Portal - Gmail SMTP Configuration" -ForegroundColor Cyan
Write-Host "=====================================" -ForegroundColor Cyan
Write-Host ""

# Get credentials from user
$emailAddress = Read-Host "Enter your Gmail address (e.g., yourname@gmail.com)"
$appPassword = Read-Host "Enter your Gmail password or App Password" -AsSecureString

# Convert secure string to plain text for joining
$ptr = [System.Runtime.InteropServices.Marshal]::SecureStringToCoTaskMemUnicode($appPassword)
$plainPassword = [System.Runtime.InteropServices.Marshal]::PtrToStringUni($ptr)
[System.Runtime.InteropServices.Marshal]::ZeroFreeCoTaskMemUnicode($ptr)

Write-Host ""
Write-Host "Setting environment variables..." -ForegroundColor Green

# Set environment variables (for current session only)
$env:RICS_SMTP_HOST = "smtp.gmail.com"
$env:RICS_SMTP_PORT = "587"
$env:RICS_SMTP_USERNAME = $emailAddress
$env:RICS_SMTP_PASSWORD = $plainPassword
$env:RICS_SMTP_FROM = $emailAddress

Write-Host ""
Write-Host "Environment variables set:" -ForegroundColor Green
Write-Host "  RICS_SMTP_HOST: $env:RICS_SMTP_HOST"
Write-Host "  RICS_SMTP_PORT: $env:RICS_SMTP_PORT"
Write-Host "  RICS_SMTP_USERNAME: $env:RICS_SMTP_USERNAME"
Write-Host "  RICS_SMTP_FROM: $env:RICS_SMTP_FROM"
Write-Host "  RICS_SMTP_PASSWORD: ••••••• (hidden)"
Write-Host ""
Write-Host "✓ Configuration ready!" -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "1. Start the server with: python serve_with_range.py"
Write-Host "2. Go to http://localhost:8080/login.html"
Write-Host "3. Click Reset Password tab and test with a registered user email"
Write-Host ""
Write-Host "The password reset code will be sent to their registered Gmail address."
