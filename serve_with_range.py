from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
import os
import re


class RangeRequestHandler(SimpleHTTPRequestHandler):
    """Simple static server with HTTP Range support for MP4 seeking."""

    def send_head(self):
        path = self.translate_path(self.path)
        if os.path.isdir(path):
            return super().send_head()

        ctype = self.guess_type(path)
        try:
            f = open(path, "rb")
        except OSError:
            self.send_error(404, "File not found")
            return None

        fs = os.fstat(f.fileno())
        size = fs.st_size
        range_header = self.headers.get("Range")

        if range_header:
            match = re.match(r"bytes=(\d*)-(\d*)", range_header)
            if match:
                start_s, end_s = match.groups()
                start = int(start_s) if start_s else 0
                end = int(end_s) if end_s else size - 1
                if start > end or end >= size:
                    self.send_error(416, "Requested Range Not Satisfiable")
                    f.close()
                    return None

                self.send_response(206)
                self.send_header("Content-type", ctype)
                self.send_header("Accept-Ranges", "bytes")
                self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
                self.send_header("Content-Length", str(end - start + 1))
                self.send_header("Last-Modified", self.date_time_string(fs.st_mtime))
                self.end_headers()

                f.seek(start)
                self._range = (start, end)
                return f

        self.send_response(200)
        self.send_header("Content-type", ctype)
        self.send_header("Content-Length", str(size))
        self.send_header("Last-Modified", self.date_time_string(fs.st_mtime))
        self.send_header("Accept-Ranges", "bytes")
        self.end_headers()
        self._range = None
        return f

    def copyfile(self, source, outputfile):
        range_info = getattr(self, "_range", None)
        if range_info is None:
            return super().copyfile(source, outputfile)

        start, end = range_info
        remaining = end - start + 1
        chunk_size = 64 * 1024
        while remaining > 0:
            read_size = min(chunk_size, remaining)
            data = source.read(read_size)
            if not data:
                break
            outputfile.write(data)
            remaining -= len(data)


def main():
    os.chdir(Path(__file__).parent)
    server = ThreadingHTTPServer(("0.0.0.0", 8080), RangeRequestHandler)
    print("Serving with range support on http://localhost:8080")
    server.serve_forever()


if __name__ == "__main__":
    main()
