#!/usr/bin/env python3
import socket
import threading
import select
import signal
import sys
import time
import getopt

# Listen
LISTENING_ADDR = '0.0.0.0'
LISTENING_PORT = sys.argv[1]

# Password protection (leave empty to disable)
PASS = ''

# Constants
BUFLEN = 4096 * 4
TIMEOUT = 60
DEFAULT_HOST = '127.0.0.1:109'
RESPONSE = ('HTTP/1.1 101 <b><u><font color="blue">'
            '(HTTP)Server By NiLphreakz</font></b>\r\n\r\n\r\n\r\n'
            'Content-Length: 104857600000\r\n\r\n').encode()

class Server(threading.Thread):
    def __init__(self, host, port):
        super().__init__()
        self.running = False
        self.host = host
        self.port = port
        self.threads = []
        self.threadsLock = threading.Lock()
        self.logLock = threading.Lock()

    def run(self):
        self.soc = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.soc.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.soc.settimeout(2)
        self.soc.bind((self.host, int(self.port)))
        self.soc.listen(0)
        self.running = True

        try:
            while self.running:
                try:
                    c, addr = self.soc.accept()
                    c.setblocking(1)
                    conn = ConnectionHandler(c, self, addr)
                    conn.start()
                    self.addConn(conn)
                except socket.timeout:
                    continue
        finally:
            self.running = False
            self.soc.close()

    def printLog(self, log):
        with self.logLock:
            print(log)

    def addConn(self, conn):
        with self.threadsLock:
            if self.running:
                self.threads.append(conn)

    def removeConn(self, conn):
        with self.threadsLock:
            if conn in self.threads:
                self.threads.remove(conn)

    def close(self):
        self.running = False
        with self.threadsLock:
            for c in list(self.threads):
                c.close()


class ConnectionHandler(threading.Thread):
    def __init__(self, client, server, addr):
        super().__init__()
        self.clientClosed = False
        self.targetClosed = True
        self.client = client
        self.server = server
        self.addr = addr
        self.client_buffer = b''
        self.log = f'Connection: {addr}'

    def close(self):
        if not self.clientClosed:
            try:
                self.client.shutdown(socket.SHUT_RDWR)
            except:
                pass
            self.client.close()
            self.clientClosed = True

        if hasattr(self, 'target') and not self.targetClosed:
            try:
                self.target.shutdown(socket.SHUT_RDWR)
            except:
                pass
            self.target.close()
            self.targetClosed = True

    def run(self):
        try:
            self.client_buffer = self.client.recv(BUFLEN)
            if not self.client_buffer:
                return

            headers = self.client_buffer.decode(errors='ignore')
            hostPort = self.findHeader(headers, 'X-Real-Host') or DEFAULT_HOST
            split = self.findHeader(headers, 'X-Split')

            if split:
                self.client.recv(BUFLEN)

            passwd = self.findHeader(headers, 'X-Pass')

            if PASS and passwd == PASS:
                self.method_CONNECT(hostPort)
            elif PASS and passwd != PASS:
                self.client.send(b'HTTP/1.1 400 WrongPass!\r\n\r\n')
            elif hostPort.startswith('127.0.0.1') or hostPort.startswith('localhost'):
                self.method_CONNECT(hostPort)
            else:
                self.client.send(b'HTTP/1.1 403 Forbidden!\r\n\r\n')

        except Exception as e:
            self.log += f' - error: {str(e)}'
            self.server.printLog(self.log)
        finally:
            self.close()
            self.server.removeConn(self)

    def findHeader(self, headers, key):
        for line in headers.split('\r\n'):
            if line.lower().startswith(key.lower() + ':'):
                return line.split(':', 1)[1].strip()
        return ''

    def connect_target(self, host):
        if ':' in host:
            host, port = host.split(':', 1)
            port = int(port)
        else:
            port = 443 if self.method == 'CONNECT' else int(LISTENING_PORT)

        addr_info = socket.getaddrinfo(host, port)[0]
        self.target = socket.socket(addr_info[0], addr_info[1], addr_info[2])
        self.target.connect(addr_info[4])
        self.targetClosed = False

    def method_CONNECT(self, path):
        self.log += f' - CONNECT {path}'
        self.connect_target(path)
        self.client.sendall(RESPONSE)
        self.client_buffer = b''
        self.server.printLog(self.log)
        self.doCONNECT()

    def doCONNECT(self):
        sockets = [self.client, self.target]
        count = 0

        while True:
            count += 1
            rlist, _, elist = select.select(sockets, [], sockets, 3)
            if elist:
                break
            if rlist:
                for s in rlist:
                    try:
                        data = s.recv(BUFLEN)
                        if not data:
                            return
                        if s is self.client:
                            self.target.sendall(data)
                        else:
                            self.client.sendall(data)
                        count = 0
                    except:
                        return
            if count == TIMEOUT:
                return


def print_usage():
    print("Usage: python3 cdn-dropbear.py -p <port>")
    print("       python3 cdn-dropbear.py -b <bindAddr> -p <port>")


def parse_args(argv):
    global LISTENING_ADDR, LISTENING_PORT
    try:
        opts, _ = getopt.getopt(argv, "hb:p:", ["bind=", "port="])
        for opt, arg in opts:
            if opt in ('-h', '--help'):
                print_usage()
                sys.exit()
            elif opt in ('-b', '--bind'):
                LISTENING_ADDR = arg
            elif opt in ('-p', '--port'):
                LISTENING_PORT = int(arg)
    except getopt.GetoptError:
        print_usage()
        sys.exit(2)


def main():
    parse_args(sys.argv[1:])
    print("\n:-------PythonProxy-------:\n")
    print(f"Listening addr: {LISTENING_ADDR}")
    print(f"Listening port: {LISTENING_PORT}\n")
    print(":-------------------------:\n")
    server = Server(LISTENING_ADDR, LISTENING_PORT)
    server.start()

    try:
        while True:
            time.sleep(2)
    except KeyboardInterrupt:
        print('Stopping...')
        server.close()


if __name__ == '__main__':
    main()
