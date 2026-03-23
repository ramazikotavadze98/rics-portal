// version: 7.12.0.a.1.3
// sha: 145cb4c0e4b38c6d51e5400697fba227b80aae56
function SetBookmark(){var o=window.parent,t=window.location.href;o.SetBookmark(t.substring(t.toLowerCase().lastIndexOf("/scormcontent/")+14,t.length),document.title),o.CommitData()}SetBookmark();