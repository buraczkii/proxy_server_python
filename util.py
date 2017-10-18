import re
import socket
import time


## CONSTANTS
PROXY_USAGE_INFO = "\n\tUsage of proxy program:\n\t\t\"python3 proxy.py <port number>\"\n\n\t- The port number " \
                "must be an integer in the range [0,65535]. Many port numbers below 1000 are either reserved or" \
                   " already in use.\n\t- In addition, you may provide the argument \"open_ports\" in place of port " \
                   "number to scan all the ports on this machine to find ones open for tcp connections.\n"
BUF_SIZE = 1024
HTTP_PORT = 80
MAX_PORT_NUM = 65635

## HTTP message format constants
LINE_REGEX = "[^\\s][^(\r|\n)]*\r\n"
GET_METHOD = "GET"
HTTP_VERSION = "HTTP/1.1"
CRLF = "\r\n"
MESSAGE_END = "(" + CRLF + CRLF +")$"
DEFAULT_PATH = "/"
GET_METHOD_RE = GET_METHOD + "[^(\r|\n)]+\r\n"
HOST_HEADER_RE = "Host:[^(\r|\n)]+\r\n"
CONNECTION_HEADER_RE = "Connection:[^(\r|\n)]+\r\n"

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
MALFORMED_REQUEST_STATUS_LINE = " 400 BAD REQUEST"
METHOD_NOT_ALLOWED_RESPONSE_STATUS_LINE  = " 405 METHOD NOT ALLOWED"
HTTP_VERSION_NOT_SUPPORTED_STATUS_LINE  = " 505 HTTP VERSION NOT SUPPORTED"
status_line_dict = { "MALFORMED":MALFORMED_REQUEST_STATUS_LINE,
                     "METHOD_NOT_SUPPORTED":METHOD_NOT_ALLOWED_RESPONSE_STATUS_LINE,
                     "VERSION_NOT_SUPPORTED":HTTP_VERSION_NOT_SUPPORTED_STATUS_LINE}

# Class to wrap exceptions raised during message processing
class ProxyException(Exception):
    pass

# Current time on the server.
def now():
  return time.ctime(time.time())

# Given the command line args, grab the port number for the proxy.
def get_port_number(args):
    if(len(args) == 2):
        if(args[1].isnumeric()) and (0 <= int(args[1]) <= MAX_PORT_NUM):
            return int(args[1])
        elif(args[1] == "open_ports"):
            get_open_ports()
    print(PROXY_USAGE_INFO)
    exit()

# Scan all ports, searching for those accepting TCP connections.
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


# Formatted log header
def log_header(addr):
    return str(now() + ": Conn '" + str(addr) + "' :")

def log_header_for_web_server(addr, requester):
    return str(now() + ": Conn '" + str(addr) + "' for '" + str(requester) + "' :")

# Get HTTP response for corresponding error
def get_failure_response(error):
    status_line = status_line_dict[error.args[0]]
    return HTTP_VERSION + status_line + CRLF + CONNECTION_CLOSE_HEADER + SERVER_HEADER + CRLF

# Formatted server header for proxy
def get_server_header_for_self():
    host_name = socket.gethostname()
    host_ip = socket.gethostbyname(host_name)
    return SERVER_HEADER + host_ip + CRLF

# Formatted request line for origin web server containing the relative path
def get_request_line_for_origin_server(path):
    return GET_METHOD + " " + path + " " + HTTP_VERSION + CRLF

# Given an open TCP connection, grab bytes until enough accumulated bytes contain the full request line.
def grab_request_line(conn):
    accumulated_request = ""
    line_matcher = re.compile(LINE_REGEX)
    while True:
        bytes = conn.recv(BUF_SIZE)
        if not bytes: break
        decoded_bytes = bytes.decode()
        accumulated_request += decoded_bytes
        accumulated_request.lstrip() # RFC 2616 says leading whitespace before status line can be ignored
        if line_matcher.findall(accumulated_request):
            break
    return accumulated_request

# Parse the request line and return the server name and file path
def parse_request_line(s, addr):
    tokens = s.split()

    if not len(tokens) == 3:
        print(log_header(addr), "Error: Request line does not have 3 tokens separated by spaces. Request line: " + s)
        raise ProxyException("MALFORMED")
    if not tokens[0] == GET_METHOD:
        print(log_header(addr), "Error: Encountered a method that was not 'GET'. Request line: " + s)
        raise ProxyException("METHOD_NOT_SUPPORTED")
    if not tokens[2] == HTTP_VERSION:
        print(log_header(addr), "Error: Encountered a http version that was not 1.1. Request line: " + s)
        raise ProxyException("VERSION_NOT_SUPPORTED")

    server_name, file_path = parse_uri(tokens[1], addr)
    file_path = ("/" + file_path) if file_path else DEFAULT_PATH
    return server_name, file_path

# Parse the URI and extract the server host name and requested file path
def parse_uri(s, addr):
    try:
        match = re.split(SCHEME_RE, s)
        URI = match.pop()
        match2 = re.split(HOST_NAME_RE, URI, 1)
        path_name = match2.pop()  # last
        host_name = match2.pop()  # second to last
        return host_name, path_name
    except:
        print(log_header(addr), "Error: Encountered exception when trying to parse URI. URI:" + s)
        raise ProxyException("MALFORMED")

# Adjust the headers for the outgoing request. Update the request line, and host and connection headers.
def adjust_headers_for_request(request, path, server_name):
    new_request_line = get_request_line_for_origin_server(path)

    request_line, rest = request.split("\r\n", 1)
    new_request_line += CONNECTION_CLOSE_HEADER
    new_request_line += HOST_HEADER + server_name + CRLF

    rest = re.sub(CONNECTION_HEADER_RE, "", rest)
    rest = re.sub(HOST_HEADER_RE, "", rest)
    return (new_request_line + rest)