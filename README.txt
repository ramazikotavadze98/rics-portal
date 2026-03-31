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
- Learner accounts: create in login page (Register Learner tab)
- Admin credentials are configured server-side in serve_with_range.py or via env vars:
  - RICS_ADMIN_USERNAME (default: admin)
  - RICS_ADMIN_PASSWORD (default: admin123123)
- Learner portal after login: http://localhost:8080/index.html
- Admin dashboard: http://localhost:8080/admin.html

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
