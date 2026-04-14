BAUMER RICS TRAINING PACKAGE

Contents
- rics_FULL/ : all RICS modules and SCORM content
- rics_videos/ : local MP4 videos
- index.html : learner portal
- login.html : login and learner registration
- admin.html : admin dashboard
- lesson_structure.json : extracted sidebar structure
- make_quiz_dashboard.py : portal generator script
- extraction scripts (*.js, *.py) : helper/research scripts

How to run locally
1) Open terminal in this folder.
2) Start local server:
   python serve_with_range.py
3) Open in browser:
   http://localhost:8080/login.html

Login and admin
- Learner accounts: create in login page (Register Learner tab) with any email provider
- Password reset: use Reset Password tab (by username, email, or mobile number)
- Reset delivery options:
  - Email delivery: Works with any email provider (Gmail, Hotmail, Yahoo, etc.). Requires SMTP setup.
  - SMS/Mobile: Reset code is printed to server terminal logs for testing
  - Local fallback: Always prints reset code to server terminal logs
- SMTP env vars (configure to enable email password reset delivery):
  Example using Gmail with 2FA (recommended):
  - RICS_SMTP_HOST=smtp.gmail.com
  - RICS_SMTP_PORT=587
  - RICS_SMTP_USERNAME=<your_gmail@gmail.com>
  - RICS_SMTP_PASSWORD=<your_google_app_password>
  - RICS_SMTP_FROM=<your_gmail@gmail.com> (optional; defaults to username)
  
  For other email providers (Hotmail, Yahoo, etc.), use your provider's SMTP server:
  - Check your email provider's help for SMTP hostname and port
  

Progress tracking
- Users, sessions, and progress are stored in SQLite database file rics_portal.db.
- Data is shared across devices that connect to the same host server.
- Admin dashboard shows all learner progress and last activity timestamps.

Video seeking note
- Use the range server above for large MP4 files. It enables fast-forward/seek.

LAN sharing
- Find your IP with: ipconfig
- Share URL with others on same network:
  http://<YOUR_IP>:8080/login.html

Notes
- Some modules require LMS behavior and may be best opened through their SCORM driver launcher.
- Preferred launcher path per module:
  rics_FULL/<module_id>/scormdriver/indexAPI.html
