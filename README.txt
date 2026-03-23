BAUMER RICS TRAINING PACKAGE

Contents
- rics_FULL/ : all RICS modules and SCORM content
- rics_videos/ : local MP4 videos
- LOCAL_STUDY_PORTAL.html : main local study portal
- lesson_structure.json : extracted sidebar structure
- make_quiz_dashboard.py : portal generator script
- extraction scripts (*.js, *.py) : helper/research scripts

How to run locally
1) Open terminal in this folder.
2) Start local server:
   python serve_with_range.py
3) Open in browser:
   http://localhost:8080/LOCAL_STUDY_PORTAL.html

Video seeking note
- Use the range server above for large MP4 files. It enables fast-forward/seek.

LAN sharing
- Find your IP with: ipconfig
- Share URL with others on same network:
  http://<YOUR_IP>:8080/LOCAL_STUDY_PORTAL.html

Notes
- Some modules require LMS behavior and may be best opened through their SCORM driver launcher.
- Preferred launcher path per module:
  rics_FULL/<module_id>/scormdriver/indexAPI.html
