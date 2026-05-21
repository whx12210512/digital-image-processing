import http.server
import ssl
import os
import socketserver

os.chdir(os.path.dirname(os.path.abspath(__file__)))

PORT = 8443

class ThreadingHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    allow_reuse_address = True
    daemon_threads = True

server_address = ('0.0.0.0', PORT)
httpd = ThreadingHTTPServer(server_address, http.server.SimpleHTTPRequestHandler)

ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
ctx.load_cert_chain('cert.pem', 'key.pem')
httpd.socket = ctx.wrap_socket(httpd.socket, server_side=True)

print(f'HTTPS Server running on https://0.0.0.0:{PORT}')
print('Press Ctrl+C to stop.')
httpd.serve_forever()
