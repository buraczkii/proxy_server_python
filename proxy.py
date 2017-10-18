import socket
import re
import sys
import _thread
import util

def main():
    host_name = socket.gethostname()
    host_ip = socket.gethostbyname(host_name)
    port_num = util.get_port_number(sys.argv)
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind((host_ip, port_num))
    except Exception:
        print(util.now(), "Error binding to port. Choose another port number.\n")
        exit()

    s.listen()
    print(util.now() + ': Proxy server started. Waiting for connection...')
    while True:
        conn, addr = s.accept()
        print(util.now()+': Server connected by', addr)
        _thread.start_new_thread(worker, (conn, addr))

def worker(client_conn, addr):
    try:
        print(util.log_header(addr), "Started thread for this new connection.")
        line_matcher = re.compile(util.LINE_REGEX)
        acc_request = util.grab_request_line(client_conn)
        request_line = line_matcher.findall(acc_request)[0]

        try:
            origin_server, file_path = util.parse_request_line(request_line, addr)
        except util.ProxyException as p:
            res = util.get_failure_response(p)
            print(util.log_header(addr), "Something was wrong with the request from client. Closing connection.")
            client_conn.sendall(str.encode(res))
            return

        while True:
            if re.findall(util.MESSAGE_END, acc_request): break # If end of message received, break
            bytes = client_conn.recv(util.BUF_SIZE)
            if not bytes: break
            acc_request += bytes.decode()
        print(util.log_header(addr), "Proxy has received the following request:\n", acc_request)
        request = util.adjust_headers_for_request(acc_request, file_path, origin_server)

        server_conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_addr = (origin_server, util.HTTP_PORT)

        server_conn.connect((origin_server, util.HTTP_PORT))
        server_conn.sendall(str.encode(request))
        print(util.log_header_for_web_server(server_addr, addr),
              'Connected to origin web server. Request sent to server:\n', request)

        try:
            server_response = b''
            while True:
                bytes = server_conn.recv(util.BUF_SIZE)
                if not bytes: break
                server_response += bytes
            print(util.log_header_for_web_server(server_addr, addr),
                  'Received response from server and forwarded to client. Closing connection.')
        except Exception:
            print(util.log_header_for_web_server(server_addr, addr),'Something went wrong. Closing connection.')
            return
        finally:
            server_conn.close()

        # Send the server's response back to the client and close the connection
        client_conn.sendall(server_response)
        print(util.log_header(addr), "Connection closed with client.")
    except:
        print(util.log_header(addr), "Something went wrong, Connection closed.")
    finally:
        client_conn.close()
        exit()

###############################################################
# Start the proxy server
try:
    main()
except:
    exit()