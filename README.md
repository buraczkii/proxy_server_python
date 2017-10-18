### CS5700 Programming Assignment 2
#### Susanna Edens | Oct. 18, 2017

#### 0. Included in this Repo
`proxy.py` : python3 file containing script to start up proxy server and serve requests

`util.py` : file containing auxilliary functions to the proxy such as logging and parsing

#### 1. How to start the proxy server
Usage of proxy program:
```bash
$ python3 proxy.py <port number>
```
- The port number must be an integer in the range [0,65535]. Many port numbers below 1000 are either reserved or already in use so try for a higher one if you want a higher chance of connecting the first time. `8181` is usually a safe bet.
- You may provide the argument `"open_ports"` in place of `<port number>` to scan all the ports on this machine to find one available for tcp connections. This can take a couple minutes.


#### 2. How to connect to proxy server

**Using your browser**:

Follow instructions specific to your browser on how to configure a proxy to route requests to. The proxy runs on your machine so for the server name, enter the name or IP of your own machine (typically `127.0.0.1` works). For the port number, use the port number that you used to start the proxy.

#### 3. Parsing the HTTP request from the client
First, the proxy will parse the request from the client. If the parsing is successful, the request will be forwarded to the origin web server.

If parsing is not successful, the response sent to the client will differ according to the error encountered:
- If the method is malformed in some way, the proxy will send a HTTP response with the status code: 400 BAD REQUEST
- The proxy only supports GET methods. If the method in the request is not GET, the client will receive a HTTP response with the status code: 405 METHOD NOT ALLOWED
- If the HTTP version in the request line of the request is not 1.1, the client will receive a HTTP response with the status code 505 HTTP VERSION NOT SUPPORTED


Expectations that the proxy has for the incoming request:
- The request must be in ascii
- The request must terminate in 2 carriage-return line-feed pairs ("\r\n\r\n"). Since the proxy server only supports GET methods, it assumes that there is no body associated with the incoming request.
- You must follow the host name in the URI with a forward slash '/'. This is the default path.
- The proxy only supports http requests, not https.

#### 5. Forwarding server response to client
The response is forwarded to the client mostly unchanged. The only possible change will be to the connection header. If the connection header is missing or indicates a persistent connection, the response will be altered to include a header indicating non-persistent connection. The new connection header is: `Connection: close\r\n`.

#### 6. Multithreading
The proxy server waits for incoming connections. It starts a new worker thread to handle the new connection. This thread will run for as long as the tcp connection lives. The thread takes care of parsing the client's request, creating an additional tcp connection to the server, and forwarding the response back to the client. The connection with the client is closed when the response from the web server is sent successfully OR when an error occurs.

#### 7. Logging
General logging statements from the proxy server have the following format:
```bash
[Time] [message]
```
Logging statements that are specific to a tcp connection have the following format:
```bash
[Time] - Conn '([host],[port])': [message]
```
Logging statements that are specific to a tcp connection with the origin web server have the following format:
```bash
[Time] - Conn '([server_host],[port])' for '([client],[port])': [message]
```
#### 8. Additional Notes

RFC 2616 lists requirements for proxy servers such as:

    _If the response is being forwarded through a proxy, the proxy application MUST NOT modify the Server response-header. Instead, it SHOULD include a Via field (as described in section 14.45)._

I did not modify the server header from the origin server, as required. However, I did not include a Via path either.

When the request from the client causes failure inside the proxy before the request is forwarded to the server, the proxy returns a failure HTTP response depending on the case. These failure responses from the server include a server header as follows: `Server: secret-proxy-server`.

