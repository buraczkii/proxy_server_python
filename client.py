import socket
import sys

MAX_BUF_SIZE = 1024

############### TEST CLIENT FOR PROXY SERVER ###############
args = sys.argv
port_num = int(args[1])
request = args[2]
server_name = socket.gethostname()

s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.connect((server_name, port_num))
print('Connected to server ', server_name)

s.sendall(str.encode("GET www.northeastern.com HTTP/1.1\r\nConnection: close\r\n\r\n"))

response = ""
data = s.recv(MAX_BUF_SIZE)
while data:
  response += data.decode("ascii")
  data = s.recv(MAX_BUF_SIZE)

print("response received: ", response)
s.close()