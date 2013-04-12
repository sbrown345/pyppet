#!/usr/bin/env python

'''
Python WebSocket library with support for "wss://" encryption.
Copyright 2011 Joel Martin
Licensed under LGPL version 3 (see docs/LICENSE.LGPL-3)

Supports following protocol versions:
    - http://tools.ietf.org/html/draft-ietf-hybi-thewebsocketprotocol-07
    - http://tools.ietf.org/html/draft-ietf-hybi-thewebsocketprotocol-10
    - http://tools.ietf.org/html/rfc6455

You can make a cert/key with openssl using:
openssl req -new -x509 -days 365 -nodes -out self.pem -keyout self.pem
as taken from http://docs.python.org/dev/library/ssl.html#certificates

------------------------------------------------------------------------
WebsockSimplify 0.0.1
(simplified fork of Joel Martin's Websockify)
by Brett Hartshorn 2013
------------------------------------------------------------------------

'''
import threading
import os, sys, time, errno, signal, socket, traceback, select
import array, struct
from base64 import b64encode, b64decode

# Imports that vary by python version

# python 3.0 differences
if sys.hexversion > 0x3000000:
    b2s = lambda buf: buf.decode('latin_1')
    s2b = lambda s: s.encode('latin_1')
    s2a = lambda s: s
else:
    b2s = lambda buf: buf  # No-op
    s2b = lambda s: s      # No-op
    s2a = lambda s: [ord(c) for c in s]
try:    from io import StringIO
except: from cStringIO import StringIO
try:    from http.server import SimpleHTTPRequestHandler
except: from SimpleHTTPServer import SimpleHTTPRequestHandler

# python 2.6 differences
try:    from hashlib import sha1
except: from sha import sha as sha1

# python 2.5 differences
try:
    from struct import pack, unpack_from
except:
    from struct import pack
    def unpack_from(fmt, buf, offset=0):
        slice = buffer(buf, offset, struct.calcsize(fmt))
        return struct.unpack(fmt, slice)

# Degraded functionality if these imports are missing
for mod, sup in [('numpy', 'HyBi protocol'), ('ssl', 'TLS/SSL/wss')]:
    try:
        globals()[mod] = __import__(mod)
    except ImportError:
        globals()[mod] = None
        print("WARNING: no '%s' module, %s is slower or disabled" % (
            mod, sup))


#class WebSocketServer( object ):
class WebSocketServer( threading.local ):
    """
    WebSockets server class.
    Must be sub-classed with new_client method definition.

    threading.local note: if you define an __init__ method, it will be
    called each time the local object is used in a separate thread.  This
    is necessary to initialize each thread's dictionary. Note that subclasses can define slots, but they are not thread
    local. They are shared across threads.

    """
    __slots__ = ('verbose', 'listen_socket', 'ssl_only', 'on_client_read_ready', 'on_client_write_ready', 'on_new_client')

    buffer_size = 65536

    server_handshake_hybi = """HTTP/1.1 101 Switching Protocols\r
Upgrade: websocket\r
Connection: Upgrade\r
Sec-WebSocket-Accept: %s\r
"""

    GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"

    policy_response = """<cross-domain-policy><allow-access-from domain="*" to-ports="*" /></cross-domain-policy>\n"""

    # An exception before the WebSocket connection was established
    class EClose(Exception):
        def __init__(self, msg):
            print('websocket error:', msg)
            import os
            os.abort() # crashing so the thread can halt everything.

    # An exception while the WebSocket client was connected
    class CClose(Exception):
        def __init__(self, msg):
            print('websocket error:', msg)
            import os
            os.abort() # crashing so the thread can halt everything.

    def initialize(self, listen_host='', listen_port=None, source_is_ipv6=False,
            verbose=False, cert='', key='', ssl_only=None, web='',
            run_once=False, timeout=0, idle_timeout=0, read_callback=None, write_callback=None, new_client_callback=None):

        self.on_client_write_ready = write_callback
        self.on_client_read_ready = read_callback
        self.on_new_client = new_client_callback

        # settings
        self.verbose        = verbose
        self.listen_host    = listen_host
        self.listen_port    = listen_port
        self.prefer_ipv6    = source_is_ipv6
        self.ssl_only       = ssl_only
        self.run_once       = run_once
        self.timeout        = timeout
        self.idle_timeout   = idle_timeout
        
        self.launch_time    = time.time()
        self.ws_connection  = False
        self.handler_id     = 1

        # Make paths settings absolute
        self.cert = os.path.abspath(cert)
        self.key = self.web = ''
        if key:
            self.key = os.path.abspath(key)
        if web:
            self.web = os.path.abspath(web)


        # Sanity checks
        if not ssl and self.ssl_only:
            raise Exception("No 'ssl' module and SSL-only specified")

        # Show configuration
        print("WebSocket server settings:")
        print("  - Listen on %s:%s" % (
                self.listen_host, self.listen_port))
        print("  - Flash security policy server")
        if self.web:
            print("  - Web server. Web root: %s" % self.web)
        if ssl:
            if os.path.exists(self.cert):
                print("  - SSL/TLS support")
                if self.ssl_only:
                    print("  - Deny non-SSL/TLS connections")
            else:
                print("  - No SSL/TLS support (no cert file)")
        else:
            print("  - No SSL/TLS support (no 'ssl' module)")


    #
    # WebSocketServer static methods
    #

    @staticmethod
    def socket(host, port=None, connect=False, prefer_ipv6=False, unix_socket=None, use_ssl=False):
        """ Resolve a host (and optional port) to an IPv4 or IPv6
        address. Create a socket. Bind to it if listen is set,
        otherwise connect to it. Return the socket.
        """
        flags = 0
        if host == '':
            host = None
        if connect and not (port or unix_socket):
            raise Exception("Connect mode requires a port")
        if use_ssl and not ssl:
            raise Exception("SSL socket requested but Python SSL module not loaded.");
        if not connect and use_ssl:
            raise Exception("SSL only supported in connect mode (for now)")
        if not connect:
            flags = flags | socket.AI_PASSIVE
            
        if not unix_socket:
            addrs = socket.getaddrinfo(host, port, 0, socket.SOCK_STREAM,
                    socket.IPPROTO_TCP, flags)
            if not addrs:
                raise Exception("Could not resolve host '%s'" % host)
            addrs.sort(key=lambda x: x[0])
            if prefer_ipv6:
                addrs.reverse()
            sock = socket.socket(addrs[0][0], addrs[0][1])
            if connect:
                sock.connect(addrs[0][4])
                if use_ssl:
                    sock = ssl.wrap_socket(sock)
            else:
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                sock.bind(addrs[0][4])
                sock.listen(100)
        else:    
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            sock.connect(unix_socket)

        return sock


    @staticmethod
    def unmask(buf, hlen, plen):
        pstart = hlen + 4
        pend = pstart + plen
        if numpy:
            b = c = s2b('')
            if plen >= 4:
                mask = numpy.frombuffer(buf, dtype=numpy.dtype('<u4'),
                        offset=hlen, count=1)
                data = numpy.frombuffer(buf, dtype=numpy.dtype('<u4'),
                        offset=pstart, count=int(plen / 4))
                #b = numpy.bitwise_xor(data, mask).data
                b = numpy.bitwise_xor(data, mask).tostring()

            if plen % 4:
                #print("Partial unmask")
                mask = numpy.frombuffer(buf, dtype=numpy.dtype('B'),
                        offset=hlen, count=(plen % 4))
                data = numpy.frombuffer(buf, dtype=numpy.dtype('B'),
                        offset=pend - (plen % 4),
                        count=(plen % 4))
                c = numpy.bitwise_xor(data, mask).tostring()
            return b + c
        else:
            # Slower fallback
            mask = buf[hlen:hlen+4]
            data = array.array('B')
            mask = s2a(mask)
            data.fromstring(buf[pstart:pend])
            for i in range(len(data)):
                data[i] ^= mask[i % 4]
            return data.tostring()

    @staticmethod
    def encode_hybi(buf, opcode, base64=False):
        """ Encode a HyBi style WebSocket frame.
        Optional opcode:
            0x0 - continuation
            0x1 - text frame (base64 encode buf)
            0x2 - binary frame (use raw buf)
            0x8 - connection close
            0x9 - ping
            0xA - pong
        """
        if base64:
            buf = b64encode(buf)

        b1 = 0x80 | (opcode & 0x0f) # FIN + opcode
        payload_len = len(buf)
        if payload_len <= 125:
            header = pack('>BB', b1, payload_len)
        elif payload_len > 125 and payload_len < 65536:
            header = pack('>BBH', b1, 126, payload_len)
        elif payload_len >= 65536:
            header = pack('>BBQ', b1, 127, payload_len)

        #print("Encoded: %s" % repr(header + buf))

        return header + buf, len(header), 0

    @staticmethod
    def decode_hybi(buf, base64=False):
        """ Decode HyBi style WebSocket packets.
        Returns:
            {'fin'          : 0_or_1,
             'opcode'       : number,
             'masked'       : boolean,
             'hlen'         : header_bytes_number,
             'length'       : payload_bytes_number,
             'payload'      : decoded_buffer,
             'left'         : bytes_left_number,
             'close_code'   : number,
             'close_reason' : string}
        """

        f = {'fin'          : 0,
             'opcode'       : 0,
             'masked'       : False,
             'hlen'         : 2,
             'length'       : 0,
             'payload'      : None,
             'left'         : 0,
             'close_code'   : 1000,
             'close_reason' : ''}

        blen = len(buf)
        f['left'] = blen

        if blen < f['hlen']:
            return f # Incomplete frame header

        b1, b2 = unpack_from(">BB", buf)
        f['opcode'] = b1 & 0x0f
        f['fin'] = (b1 & 0x80) >> 7
        f['masked'] = (b2 & 0x80) >> 7

        f['length'] = b2 & 0x7f

        if f['length'] == 126:
            f['hlen'] = 4
            if blen < f['hlen']:
                return f # Incomplete frame header
            (f['length'],) = unpack_from('>xxH', buf)
        elif f['length'] == 127:
            f['hlen'] = 10
            if blen < f['hlen']:
                return f # Incomplete frame header
            (f['length'],) = unpack_from('>xxQ', buf)

        full_len = f['hlen'] + f['masked'] * 4 + f['length']

        if blen < full_len: # Incomplete frame
            return f # Incomplete frame header

        # Number of bytes that are part of the next frame(s)
        f['left'] = blen - full_len

        # Process 1 frame
        if f['masked']:
            # unmask payload
            f['payload'] = WebSocketServer.unmask(buf, f['hlen'],
                                                  f['length'])
        else:
            print("Unmasked frame: %s" % repr(buf))
            f['payload'] = buf[(f['hlen'] + f['masked'] * 4):full_len]

        if base64 and f['opcode'] in [1, 2]:
            try:
                f['payload'] = b64decode(f['payload'])
            except:
                print("Exception while b64decoding buffer: %s" %
                        repr(buf))
                raise

        if f['opcode'] == 0x08:
            if f['length'] >= 2:
                f['close_code'] = unpack_from(">H", f['payload'])[0]
            if f['length'] > 3:
                f['close_reason'] = f['payload'][2:]

        return f


    #
    # WebSocketServer logging/output functions
    #

    def traffic(self, token="."):
        """ Show traffic flow in verbose mode. """
        if self.verbose: print(token)

    def msg(self, msg):
        """ Output message with handler_id prefix. """
        print("% 3d: %s" % (self.handler_id, msg))

    def vmsg(self, msg):
        """ Same as msg() but only if verbose. """
        if self.verbose:
            self.msg(msg)

    #
    # Main WebSocketServer methods
    #
    def send_frames(self, bufs=None):
        """ Encode and send WebSocket frames. Any frames already
        queued will be sent first. If buf is not set then only queued
        frames will be sent. Returns the number of pending frames that
        could not be fully sent. If returned pending frames is greater
        than 0, then the caller should call again when the socket is
        ready. """

        tdelta = int(time.time()*1000) - self.start_time

        if bufs:
            for buf in bufs:
                if self.base64:
                    encbuf, lenhead, lentail = self.encode_hybi(buf, opcode=1, base64=True)
                else:
                    encbuf, lenhead, lentail = self.encode_hybi(buf, opcode=2, base64=False)

                if self.rec:
                    self.rec.write("%s,\n" %
                            repr("{%s{" % tdelta
                                + encbuf[lenhead:len(encbuf)-lentail]))

                self.send_parts.append(encbuf)

        while self.send_parts:
            # Send pending frames
            buf = self.send_parts.pop(0)
            sent = self.client.send(buf)

            if sent == len(buf):
                self.traffic("<")
            else:
                self.traffic("<.")
                self.send_parts.insert(0, buf[sent:])
                break

        return len(self.send_parts)

    def recv_frames(self):
        """ Receive and decode WebSocket frames.

        Returns:
            (bufs_list, closed_string)
        """

        closed = False
        bufs = []
        tdelta = int(time.time()*1000) - self.start_time

        buf = self.client.recv(self.buffer_size)
        if len(buf) == 0:
            closed = {'code': 1000, 'reason': "Client closed abruptly"}
            return bufs, closed

        if self.recv_part:
            # Add partially received frames to current read buffer
            buf = self.recv_part + buf
            self.recv_part = None

        while buf:
            frame = self.decode_hybi(buf, base64=self.base64)
            #print("Received buf: %s, frame: %s" % (repr(buf), frame))

            if frame['payload'] == None:
                # Incomplete/partial frame
                self.traffic("}.")
                if frame['left'] > 0:
                    self.recv_part = buf[-frame['left']:]
                break
            else:
                if frame['opcode'] == 0x8: # connection close
                    closed = {'code': frame['close_code'],
                              'reason': frame['close_reason']}
                    break

            self.traffic("}")

            if self.rec:
                start = frame['hlen']
                end = frame['hlen'] + frame['length']
                if frame['masked']:
                    recbuf = WebSocketServer.unmask(buf, frame['hlen'],
                                                   frame['length'])
                else:
                    recbuf = buf[frame['hlen']:frame['hlen'] +
                                               frame['length']]
                self.rec.write("%s,\n" %
                        repr("}%s}" % tdelta + recbuf))


            bufs.append(frame['payload'])

            if frame['left']:
                buf = buf[-frame['left']:]
            else:
                buf = ''

        return bufs, closed

    def send_close(self, code=1000, reason=''):
        """ Send a WebSocket orderly close frame. """

        msg = pack(">H%ds" % len(reason), code, reason)
        buf, h, t = self.encode_hybi(msg, opcode=0x08, base64=False)
        self.client.send(buf)

    def do_websocket_handshake(self, headers, path):
        h = self.headers = headers
        print('HEADERS websocket', h)
        self.path = path

        prot = 'WebSocket-Protocol'
        protocols = h.get('Sec-'+prot, h.get(prot, '')).split(',')

        ver = h.get('Sec-WebSocket-Version')
        if ver:
            # HyBi/IETF version of the protocol

            # HyBi-07 report version 7
            # HyBi-08 - HyBi-12 report version 8
            # HyBi-13 reports version 13
            if ver in ['7', '8', '13']:
                self.version = "hybi-%02d" % int(ver)
            else:
                raise self.EClose('Unsupported protocol version %s' % ver)

            key = h['Sec-WebSocket-Key']

            # Choose binary if client supports it
            if 'binary' in protocols:
                self.base64 = False
            elif 'base64' in protocols:
                self.base64 = True
            else:
                raise self.EClose("Client must support 'binary' or 'base64' protocol")

            # Generate the hash value for the accept header
            accept = b64encode(sha1(s2b(key + self.GUID)).digest())

            response = self.server_handshake_hybi % b2s(accept)
            if self.base64:
                response += "Sec-WebSocket-Protocol: base64\r\n"
            else:
                response += "Sec-WebSocket-Protocol: binary\r\n"
            response += "\r\n"

        else:
            raise self.EClose("Missing Sec-WebSocket-Version header. Hixie protocols not supported.")

        return response


    CustomRequestHandler = None  ## the user can set a its own request handler for custom server app-logic

    def do_handshake(self, sock, address):
        """
        do_handshake does the following:
        - Peek at the first few bytes from the socket.
        - If the connection is Flash policy request then answer it,
          close the socket and return.
        - If the connection is an HTTPS/SSL/TLS connection then SSL
          wrap the socket.
        - Read from the (possibly wrapped) socket.
        - If we have received a HTTP GET request and the webserver
          functionality is enabled, answer it, close the socket and
          return.
        - Assume we have a WebSockets connection, parse the client
          handshake data.
        - Send a WebSockets handshake server response.
        - Return the socket for this WebSocket client.
        """
        stype = ""
        #ready = select.select([sock], [], [], 3)[0]
        #if not ready:
        #    raise self.EClose("ignoring socket not ready")
        # Peek, but do not read the data so that we have a opportunity
        # to SSL wrap the socket first
        handshake = sock.recv(1024, socket.MSG_PEEK)
        #self.msg("Handshake [%s]" % handshake)

        if handshake == "":
            raise self.EClose("ignoring empty handshake")

        elif handshake.startswith(s2b("<policy-file-request/>")):
            # Answer Flash policy request
            handshake = sock.recv(1024)
            sock.send(s2b(self.policy_response))
            #raise self.EClose("Sending flash policy response")
            return sock

        elif handshake and handshake[0] in ("\x16", "\x80", 22, 128):
            # SSL wrap the connection
            if not ssl:
                raise self.EClose("SSL connection but no 'ssl' module")
            if not os.path.exists(self.cert):
                raise self.EClose("SSL connection but '%s' not found"
                                  % self.cert)
            retsock = None
            try:
                retsock = ssl.wrap_socket(
                        sock,
                        server_side=True,
                        certfile=self.cert,
                        keyfile=self.key)
            except ssl.SSLError:
                _, x, _ = sys.exc_info()
                if x.args[0] == ssl.SSL_ERROR_EOF:
                    if len(x.args) > 1:
                        raise self.EClose(x.args[1])
                    else:
                        raise self.EClose("Got SSL_ERROR_EOF")
                else:
                    raise

            self.scheme = "wss"
            stype = "SSL/TLS (wss://)"

        elif self.ssl_only:
            raise self.EClose("non-SSL connection received but disallowed")

        else:
            retsock = sock
            self.scheme = "ws"
            stype = "Plain non-SSL (ws://)"

        ###############################################################################
        if self.CustomRequestHandler:  ## should also be a subclass of WSRequestHandler
            wsh = self.CustomRequestHandler(retsock, address)
        else:
            wsh = WSRequestHandler(retsock, address, not self.web)
        ###############################################################################
        if not hasattr(wsh,'last_code'):
            return None
        elif wsh.last_code == 101:
            # Continue on to handle WebSocket upgrade
            pass
        elif wsh.last_code == 405:
            print('error 405')
            raise self.EClose("Normal web request received but disallowed")
        elif wsh.last_code < 200 or wsh.last_code >= 300:
            print('error <200 or >=300')
            raise self.EClose(wsh.last_message)
        else:
            return None
        #elif self.verbose:
        #    raise self.EClose(wsh.last_message)
        #else:
        #    raise self.EClose("")

        assert wsh.last_code == 101
        response = self.do_websocket_handshake(wsh.headers, wsh.path)

        print("%s: %s WebSocket connection" % (address[0], stype))
        print("%s: Version %s, base64: '%s'" % (address[0],
            self.version, self.base64))
        if self.path != '/':
            self.msg("%s: Path: '%s'" % (address[0], self.path))

        # Send server WebSockets handshake response
        #self.msg("sending response [%s]" % response)
        #retsock.send(s2b(response))
        if wsh.last_code != 200:
            retsock.send(s2b(response))
            self._ws_connection = True
        else:
            self._ws_connection = False  # need this to stop caller from doing topping the websocket client.

        # Return the WebSockets socket which may be SSL wrapped
        return retsock

    def top_new_client(self, startsock, address):
        """ Do something with a WebSockets client connection. """
        # Initialize per client settings
        self.send_parts = []
        self.recv_part  = None
        self.base64     = False
        self.rec        = None
        self.start_time = int(time.time()*1000)
        print('START-TIME', self.start_time)
        # handler process
        self.ws_connection = False
        self._ws_connection = False
        #try: ## this try can be enabled to except EClose, EClose is failures the websockify api allows.
        self.client = self.do_handshake(startsock, address)  ## do_handshake will also answer a http request.
        #except self.EClose: ## TODO enable me on releases.

        if self._ws_connection:
            print('<<new websocket connection>>', self.client)
            self.ws_connection = True
            self.new_client()
        elif self.client and self.client != startsock:
            self.client.close() # close normal http request
        elif self.client:
            print('topping listener',self.client)


    def new_client(self):
        """ Do something with a WebSockets client connection. """
        #raise("WebSocketServer.new_client() must be overloaded")
        assert self.client != self.listen_socket
        self.on_new_client( self.client )

        self.websocket_active = True
        while self.websocket_active:
            #print('selecting client websocket...')
            ins, outs, excepts = select.select([self.client], [self.client], [self.client], 10)
            if excepts: self.websocket_active = False

            if outs:
                #print('outs ready...')
                data = self.on_client_write_ready( self.client )
                #self.out_bytes += len(data)
                #try:
                pending = self.send_frames( [data] )
                if pending: print('[websocket error] failed to send data', data)

            if ins:
                #print('ins ready...')
                frames, closed = self.recv_frames()
                if closed:
                    self.websocket_active = False
                else:
                    self.on_client_read_ready( self.client, frames )

            time.sleep(0.1)
        print('[websocket client thread exit]')

    def create_listener_socket(self):
        self.listen_socket = self.socket(self.listen_host, self.listen_port)
        return self.listen_socket

    def start_listener_thread(self):
        assert self.listen_socket
        #self.lock = threading._allocate_lock()
        threading._start_new_thread( self._listener_thread_loop, ())

    def _listener_thread_loop(self):
        self.active = True
        while self.active:
            ready = select.select([self.listen_socket], [], [], 1000)[0]
            if ready:
                #self.lock.acquire()
                for sock in ready:
                    print('main listener',sock)
                    startsock, address = sock.accept()
                    #self.top_new_client(startsock, address) # sets.client and calls new_client()
                    threading._start_new_thread(
                        self.top_new_client, (startsock, address)
                        )

                    print('main listener topped')
                #self.lock.release()
            print('listening...')

# HTTP handler with WebSocket upgrade support
class WSRequestHandler(SimpleHTTPRequestHandler):
    def __init__(self, req, addr, only_upgrade=False):
        self.only_upgrade = only_upgrade # only allow upgrades
        SimpleHTTPRequestHandler.__init__(self, req, addr, object())

    def do_GET(self):
        if (self.headers.get('upgrade') and
                self.headers.get('upgrade').lower() == 'websocket'):

            # Just indicate that an WebSocket upgrade is needed
            self.last_code = 101
            self.last_message = "101 Switching Protocols"
        elif self.only_upgrade:
            # Normal web request responses are disabled
            self.last_code = 405
            self.last_message = "405 Method Not Allowed"
        else:
            SimpleHTTPRequestHandler.do_GET(self)

    def send_response(self, code, message=None):
        # Save the status code
        self.last_code = code
        SimpleHTTPRequestHandler.send_response(self, code, message)

    def log_message(self, f, *args):
        # Save instead of printing
        self.last_message = f % args
