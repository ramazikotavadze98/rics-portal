// version: 7.12.0.a.1.3.2
// sha: aa9400bb2ffa242594bf64c148d55d7a3ba4f459
function SetBookmark(){var o=window.parent,t=window.location.href;o.SetBookmark(t.substring(t.toLowerCase().lastIndexOf("/scormcontent/")+14,t.length),document.title),o.CommitData()}SetBookmark();