import socket
import re
import sys
import _thread
import time

## CONSTANTS
BUF_SIZE = 1024
PROXY_USAGE_INFO = "\n\tUsage of proxy program:\n\t\t\"python3 proxy.py <port number>\"\n\n\t- The port number " \
                "must be an integer in the range [0,65535]. Many port numbers below 1000 are either reserved or" \
                   " already in use.\n\t- In addition, you may provide the argument \"open_ports\" in place of port " \
                   "number to scan all the ports on this machine to find ones open for tcp connections.\n"
HTTP_PORT = 80

## HTTP message format constants
LINE_REGEX = "[^\\s][^(\r|\n)]*\r\n"
GET_METHOD = "GET"
HTTP_VERSION = "HTTP/1.1"
CRLF = "\r\n"
MESSAGE_END = "(" + CRLF + CRLF +")$"
DEFAULT_PATH = "/index.html"

## URI constants
SCHEME_RE = "([A-za-z]+[A-Za-z0-9\+-\.]*://)" # Matches characters before the beginning of the host name
ONE_BYTE_RANGE_RE = "([0-9]|[1-9][0-9]|1[0-9][0-9]|2[0-4][0-9]|25[0-5])"
IPv4_ADDRESS_RE = ONE_BYTE_RANGE_RE + "\." + ONE_BYTE_RANGE_RE + "\." + ONE_BYTE_RANGE_RE + "\." + ONE_BYTE_RANGE_RE
REGISTERED_NAME_RE = "([^\/\:\?\#\@]+)"  # matches the server name until the path
PATH_START_RE = "\/"
HOST_NAME_RE = "(" + IPv4_ADDRESS_RE + "|" + REGISTERED_NAME_RE + ")" + PATH_START_RE

## Header constants
HOST_HEADER = "Host: "
CONNECTION_HEADER = "Connection: "
CONNECTION_CLOSE_HEADER = CONNECTION_HEADER + "close\r\n"
SERVER_HEADER = "Server: secret-proxy-server\r\n"

# Status lines
MALFORMED_REQUEST_STATUS_LINE = "400 BAD REQUEST"
METHOD_NOT_ALLOWED_RESPONSE_STATUS_LINE  = "405 METHOD NOT ALLOWED"
HTTP_VERSION_NOT_SUPPORTED_STATUS_LINE  = "505 HTTP VERSION NOT SUPPORTED"
status_line_dict = { "MALFORMED":MALFORMED_REQUEST_STATUS_LINE,
                     "METHOD_NOT_SUPPORTED":METHOD_NOT_ALLOWED_RESPONSE_STATUS_LINE,
                     "VERSION_NOT_SUPPORTED":HTTP_VERSION_NOT_SUPPORTED_STATUS_LINE}

# Class to wrap exceptions raised during message processing
class ProxyException(Exception):
    pass

def main():
    host_name = socket.gethostname()
    host_ip = socket.gethostbyname(host_name)
    port_num = get_port_number(sys.argv)
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    try:
        s.bind((host_ip, port_num))
    except Exception as e:
        print(now(), "Error binding to port. Choose another port number.\n")
        exit()

    s.listen()
    print(now() + ': Proxy server started. Waiting for connection...')
    while True:
        conn, addr = s.accept()
        print(now(), ':Server connected by', addr)
        _thread.start_new_thread(worker, (conn, addr))

# Current time on the server.
def now():
  return time.ctime(time.time())

def log_header(addr):
    return str(now() + " - Connection to: " + str(addr) + " :")

def grab_request_line(conn):
    accumulated_request = ""
    line_matcher = re.compile(LINE_REGEX)
    while True:
        bytes = conn.recv(BUF_SIZE)
        if not bytes: break
        decoded_bytes = bytes.decode("ascii")
        accumulated_request += decoded_bytes
        accumulated_request.lstrip() # RFC 2616 says leading whitespace before status line can be ignored
        if line_matcher.findall(accumulated_request): #TODO: THIS USED TO WORK AND NOW IT DOESN'T AGGH
            break
        if re.findall(LINE_REGEX, accumulated_request):  # TODO: ALTERNATIVE
            break
    return accumulated_request

def parse_request_line(s):
    tokens = s.split() #split on white spaces

    if not len(tokens) == 3:
        raise ProxyException("MALFORMED")
    if not tokens[0] == GET_METHOD:
        raise ProxyException("METHOD_NOT_SUPPORTED")
    if not tokens[2] == HTTP_VERSION:
        raise ProxyException("VERSION_NOT_SUPPORTED")
    return parse_uri(tokens[1])

def parse_uri(s):
    try:
        match = re.split(SCHEME_RE, s)
        URI = match.pop()
        match2 = re.split(HOST_NAME_RE, URI)
        path_name = match2.pop()  # last
        host_name = match2.pop()  # second to last
        return host_name, path_name
    except:
        raise ProxyException("MALFORMED")

def get_failure_response(error):
    status_line = status_line_dict[error.args[0]]
    return HTTP_VERSION + status_line + CRLF + CONNECTION_CLOSE_HEADER + SERVER_HEADER + CRLF

def adjust_headers_for_request(lines, path, server_name):
    new_request_line = get_request_line_for_origin_server(path)
    conn_header = ""
    request_line = ""
    host_line = ""
    for line in lines:
        if re.match(CONNECTION_HEADER, line): conn_header = line
        elif re.match(GET_METHOD, line): request_line = line
        elif re.match(HOST_HEADER, line): host_line = line

    lines.remove(conn_header)
    lines.remove(request_line)
    if host_line: lines.remove(host_line)
    lines.append(CONNECTION_CLOSE_HEADER)
    lines.append(HOST_HEADER + server_name + CRLF)
    return [new_request_line] + lines

# TODO: This is causing problems.
# def adjust_headers_for_response(response, line_matcher):
#     if not CONNECTION_HEADER in response:
#         return response
#
#     headers = response.split(CRLF+CRLF)[0]
#     rest = response.split(CRLF+CRLF)[1:]
#     lines = line_matcher.findall(headers)
#
#     conn_header = ""
#     for line in lines:
#         if re.match(CONNECTION_HEADER, line):
#             conn_header = line
#             break
#     if conn_header: lines.remove(conn_header)
#     lines.append(CONNECTION_CLOSE_HEADER)
#
#     new_response = ""
#     for line in lines:
#         new_response += line
#     new_response += CRLF # to end headers
#     for r in rest:
#         new_response += r
#     return new_response


def get_request_line_for_origin_server(path):
    return GET_METHOD + " " + path + " " + HTTP_VERSION + CRLF


def get_server_header_for_self():
    host_name = socket.gethostname()
    host_ip = socket.gethostbyname(host_name)
    return SERVER_HEADER + host_ip + CRLF


def forward_request_to_server(conn, message_lines):
    for line in message_lines:
        conn.sendall(str.encode(line))
    conn.send(str.encode(CRLF)) # to end request


def worker(client_conn, addr):
    try:
        print(log_header(addr), "Started thread for this new connection.")
        line_matcher = re.compile(LINE_REGEX)
        acc_request = grab_request_line(client_conn)
        request_line = line_matcher.findall(acc_request)[0]

        try:
            origin_server, file_path = parse_request_line(request_line)
            file_path  = ("/" + file_path) if file_path else DEFAULT_PATH
        except ProxyException as p:
            res = get_failure_response(p)
            print(log_header(addr), "Something was wrong with the request from client. Closing connection.")
            client_conn.sendall(res)
            client_conn.close()
            return

        # grab the rest of the http request from the client
        while True:
            if re.findall(MESSAGE_END, acc_request): # If end of message received, break
                break
            bytes = client_conn.recv(BUF_SIZE)
            if not bytes: break
            acc_request += bytes.decode("ascii")
        print(log_header(addr), "Proxy has received the following request:\n", acc_request)

        # Add Connection: close header for non-persistent HTTP sessions & Modify request line for origin server
        request_lines = adjust_headers_for_request(line_matcher.findall(acc_request), file_path, origin_server)

        # Make TCP connection to the "real" Web server;
        server_conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_conn.connect((origin_server, HTTP_PORT))
        print(log_header((origin_server, HTTP_PORT)), 'Connected to origin server ')

        # Send over an HTTP request;
        forward_request_to_server(server_conn, request_lines)
        server_response = ""
        while True:
            bytes = server_conn.recv(BUF_SIZE)
            if not bytes: break
            server_response += bytes.decode("ascii")
        print(server_response)
        server_conn.close()

        # Send the server's response back to the client and close the connection
        # server_response = adjust_headers_for_response(line_matcher.findall(server_response, line_matcher))
        client_conn.sendall(str.encode(server_response))
        client_conn.close()
        print(log_header(addr), "Connection closed with client.")
        exit()
    except:
        print(log_header(addr), "Something went wrong, Connection closed.")
        client_conn.close()
        exit()


def get_port_number(args):
    if(len(args) == 2):
        if(args[1].isnumeric()) and (0 <= int(args[1]) <= 65635):
            return int(args[1])
        elif(args[1] == "open_ports"):
            get_open_ports()
    print(PROXY_USAGE_INFO)
    exit()


def get_open_ports():
    print(now(), "Scanning all ports. This will take a few minutes... Press CTRL-c to cancel. \n")
    ip = "127.0.0.1"
    open_ports = []
    for port in range(0,65536):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect((ip, port))
            open_ports.append(port)
            s.close()
        except socket.error:
            continue
        except:
            exit()
    print(open_ports)
    exit()


###############################################################
# Start the proxy server. Exit gracefully/simply on exception.
try:
    main()
except:
    exit()