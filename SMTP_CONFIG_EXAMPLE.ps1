# RICS Portal SMTP Configuration
# Copy and paste these commands into PowerShell, replacing the values

# 1. Set Gmail SMTP environment variables
$env:RICS_SMTP_HOST = "smtp.gmail.com"
$env:RICS_SMTP_PORT = "587"
$env:RICS_SMTP_USERNAME = "your_email@gmail.com"           # CHANGE THIS
$env:RICS_SMTP_PASSWORD = "your_gmail_password"            # CHANGE THIS
$env:RICS_SMTP_FROM = "your_email@gmail.com"               # CHANGE THIS

# 2. Verify configuration (optional)
Write-Host "SMTP Configuration:" -ForegroundColor Green
Write-Host "Host: $env:RICS_SMTP_HOST"
Write-Host "Port: $env:RICS_SMTP_PORT"
Write-Host "Username: $env:RICS_SMTP_USERNAME"
Write-Host "From: $env:RICS_SMTP_FROM"
Write-Host ""
Write-Host "Password is set: $(if ($env:RICS_SMTP_PASSWORD) {'Yes'} else {'No'})"

# 3. Start the server
cd 'c:\Users\user\Desktop\baumer-rics-training'
python serve_with_range.py
