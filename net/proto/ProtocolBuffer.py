# Copyright 2002, Google Inc.
# Author: Keith Randall

"""
The base class for python protocol buffers, as well as classes used for
encoding and decoding.
see http://moma/eng/designdocs/infrastructure/protocol-buffer.html
for a description of what protocol buffers are and what you would
want one for.

To encode a protocol buffer message, do:
  pb = FooProto()        - make a new, empty protocol buffer object
  pb.set_...()           - set all of its fields you care about
  s = pb.Encode()        - convert to a string

To decode a protocol buffer message, do:
  pb = FooProto(s)       - make a new object, initialize from a string
  pb....()               - read values from protocol buffer object

FooProto() should be a class automatically generated by
bin/protocol-compiler (which will be a subclass of ProtocolMessage below)
"""

import struct
import array
import string
import re
from google3.pyglib.gexcept import AbstractMethod
import httplib

__all__ = ['ProtocolMessage', 'Encoder', 'Decoder',
           'ProtocolBufferDecodeError',
           'ProtocolBufferEncodeError',
           'ProtocolBufferReturnError']

URL_RE = re.compile('^(https?)://([^/]+)(/.*)$')

class ProtocolMessage:
  """
  The parent class of all protocol buffers.
  NOTE: the methods that unconditionally raise AbstractMethod are
  reimplemented by the subclasses of this class.
  Subclasses are automatically generated by tools/protocol_converter.
  Encoding methods can raise ProtocolBufferEncodeError if a value for an
  integer or long field is too large, or if any required field is not set.
  Decoding methods can raise ProtocolBufferDecodeError if they couldn't
  decode correctly, or the decoded message doesn't have all required fields.
  """

  #####################################
  # methods you should use            #
  #####################################

  def __init__(self, contents=None):
    """Construct a new protocol buffer, with optional starting contents
    in binary protocol buffer format."""
    raise AbstractMethod

  def Clear(self):
    """Erases all fields of protocol buffer (& resets to defaults
    if fields have defaults)."""
    raise AbstractMethod

  def IsInitialized(self, debug_strs=None):
    """returns true iff all required fields have been set."""
    raise AbstractMethod

  def Encode(self):
    """returns a string representing the protocol buffer object."""
    try:
      return self._CEncode()
    except AbstractMethod:
      e = Encoder()
      self.Output(e)
      return e.buffer().tostring()

  def _CEncode(self):
    """Call into C++ encode code.

    Generated protocol buffer classes will override this method to
    provide C++-based serialization. If a subclass does not
    implement this method, Encode() will fall back to
    using pure-Python encoding.
    """
    raise AbstractMethod

  def ParseFromString(self, s):
    """Reads data from the string 's'.
    Raises a ProtocolBufferDecodeError if, after successfully reading
    in the contents of 's', this protocol message is still not initialized."""
    self.Clear()
    self.MergeFromString(s)
    return

  def MergeFromString(self, s):
    """Adds in data from the string 's'.
    Raises a ProtocolBufferDecodeError if, after successfully merging
    in the contents of 's', this protocol message is still not initialized."""
    try:
      self._CMergeFromString(s)
      # _CMergeFromString() does no IsInitialized() check, so we do it here.
      dbg = []
      if not self.IsInitialized(dbg):
        raise ProtocolBufferDecodeError, '\n\t'.join(dbg)
    except AbstractMethod:
      # If we can't call into C++ to deserialize the string, use
      # the (much slower) pure-Python implementation.
      a = array.array('B')
      a.fromstring(s)
      d = Decoder(a, 0, len(a))
      self.Merge(d)  # Checks IsInitialized() for us.
      return

  def _CMergeFromString(self, s):
    """Call into C++ parsing code to merge from a string.

    Does *not* check IsInitialized() before returning.

    Generated protocol buffer classes will override this method to
    provide C++-based deserialization.  If a subclass does not
    implement this method, MergeFromString() will fall back to
    using pure-Python parsing.
    """
    raise AbstractMethod

  def __getstate__(self):
    """Return the pickled representation of the data inside protocol buffer,
    which is the same as its binary-encoded representation (as a string)."""
    return self.Encode()

  def __setstate__(self, contents_):
    """Restore the pickled representation of the data inside protocol buffer.
    Note that the mechanism underlying pickle.load() does not call __init__."""
    self.__init__(contents=contents_)

  def sendCommand(self, server, url, response, follow_redirects=1,
                  secure=0, keyfile=None, certfile=None):
    """posts the protocol buffer to the desired url on the server
    and puts the return data into the protocol buffer 'response'

    NOTE: The underlying socket raises the 'error' exception
    for all I/O related errors (can't connect, etc.).

    If 'response' is None, the server's PB response will be ignored.

    The optional 'follow_redirects' argument indicates the number
    of HTTP redirects that are followed before giving up and raising an
    exception.  The default is 1.

    If 'secure' is true, HTTPS will be used instead of HTTP.  Also,
    'keyfile' and 'certfile' may be set for client authentication.
    """
    data = self.Encode()
    if secure:
      if keyfile and certfile:
        conn = httplib.HTTPSConnection(server, key_file=keyfile,
                                       cert_file=certfile)
      else:
        conn = httplib.HTTPSConnection(server)
    else:
      conn = httplib.HTTPConnection(server)
    conn.putrequest("POST", url)
    conn.putheader("Content-Length", "%d" %len(data))
    conn.endheaders()
    conn.send(data)
    resp = conn.getresponse()
    if follow_redirects > 0 and resp.status == 302:
      m = URL_RE.match(resp.getheader('Location'))
      if m:
        protocol, server, url = m.groups()
        return self.sendCommand(server, url, response,
                                follow_redirects=follow_redirects - 1,
                                secure=(protocol == 'https'),
                                keyfile=keyfile,
                                certfile=certfile)
    if resp.status != 200:
      raise ProtocolBufferReturnError(resp.status)
    if response is not None:
      response.ParseFromString(resp.read())
    return response

  def sendSecureCommand(self, server, keyfile, certfile, url, response,
                        follow_redirects=1):
    """posts the protocol buffer via https to the desired url on the server,
    using the specified key and certificate files, and puts the return
    data int othe protocol buffer 'response'.

    See caveats in sendCommand.

    You need an SSL-aware build of the Python2 interpreter to use this command.
    (Python1 is not supported).  An SSL build of python2.2 is in
    /home/build/buildtools/python-ssl-2.2 . An SSL build of python2.3 is
    in /home/build/buildtools/python-2.3. 'googleup python23' will install
    python 2.3 (with SSL support) on a production machine.

    keyfile: Contains our private RSA key
    certfile: Contains SSL certificate for remote host
    Specify None for keyfile/certfile if you don't want to do client auth.
    """
    return self.sendCommand(server, url, response,
                            follow_redirects=follow_redirects,
                            secure=1, keyfile=keyfile, certfile=certfile)

  def __str__(self, prefix="", printElemNumber=0):
    """Returns nicely formatted contents of this protocol buffer."""
    raise AbstractMethod

  def ToASCII(self):
    """Returns the protocol buffer as a human-readable string."""
    return self._CToASCII(ProtocolMessage._SYMBOLIC_FULL_ASCII)

  def ToCompactASCII(self):
    """Returns the protocol buffer as an ASCII string.
    Tag numbers are used instead of field names.
    Defers to the C++ ProtocolPrinter class in NUMERIC mode.
    """
    return self._CToASCII(ProtocolMessage._NUMERIC_ASCII)

  def ToShortASCII(self):
    """Returns the protocol buffer as an ASCII string.
    The output is short, leaving out newlines and some other niceties.
    Defers to the C++ ProtocolPrinter class in SYMBOLIC_SHORT mode.
    """
    return self._CToASCII(ProtocolMessage._SYMBOLIC_SHORT_ASCII)

  # Note that these must be consistent with the ProtocolPrinter::Level C++
  # enum.
  _NUMERIC_ASCII = 0
  _SYMBOLIC_SHORT_ASCII = 1
  _SYMBOLIC_FULL_ASCII = 2

  def _CToASCII(self, output_format):
    """Calls into C++ ASCII-generating code.

    Generated protocol buffer classes will override this method to provide
    C++-based ASCII output.
    """
    raise AbstractMethod

  def ParseASCII(self, ascii_string):
    """Parses a string generated by ToASCII() or by the C++ DebugString()
    method, initializing this protocol buffer with its contents. This method
    raises a ValueError if it encounters an unknown field.
    """
    raise AbstractMethod

  def ParseASCIIIgnoreUnknown(self, ascii_string):
    """Parses a string generated by ToASCII() or by the C++ DebugString()
    method, initializing this protocol buffer with its contents.  Ignores
    unknown fields.
    """
    raise AbstractMethod

  #####################################
  # methods power-users might want    #
  #####################################

  def Output(self, e):
    """write self to the encoder 'e'."""
    dbg = []
    if not self.IsInitialized(dbg):
      raise ProtocolBufferEncodeError, '\n\t'.join(dbg)
    self.OutputUnchecked(e)
    return

  def OutputUnchecked(self, e):
    """write self to the encoder 'e', don't check for initialization."""
    raise AbstractMethod

  def Parse(self, d):
    """reads data from the Decoder 'd'."""
    self.Clear()
    self.Merge(d)
    return

  def Merge(self, d):
    """merges data from the Decoder 'd'."""
    self.TryMerge(d)
    dbg = []
    if not self.IsInitialized(dbg):
      raise ProtocolBufferDecodeError, '\n\t'.join(dbg)
    return

  def TryMerge(self, d):
    """merges data from the Decoder 'd'."""
    raise AbstractMethod

  def CopyFrom(self, pb):
    """copy data from another protocol buffer"""
    if (pb == self): return
    self.Clear()
    self.MergeFrom(pb)

  def MergeFrom(self, pb):
    """merge data from another protocol buffer"""
    raise AbstractMethod

  #####################################
  # helper methods for subclasses     #
  #####################################

  def lengthVarInt32(self, n):
    return self.lengthVarInt64(n)

  def lengthVarInt64(self, n):
    if n < 0:
      return 10 # ceil(64/7)
    result = 0
    while 1:
      result += 1
      n >>= 7
      if n == 0:
        break
    return result

  def lengthString(self, n):
    return self.lengthVarInt32(n) + n

  def DebugFormat(self, value):
    return "%s" % value
  def DebugFormatInt32(self, value):
    if (value <= -2000000000 or value >= 2000000000):
      return self.DebugFormatFixed32(value)
    return "%d" % value
  def DebugFormatInt64(self, value):
    if (value <= -2000000000 or value >= 2000000000):
      return self.DebugFormatFixed64(value)
    return "%d" % value
  def DebugFormatString(self, value):
    # For now we only escape the bare minimum to insure interoperabilty
    # and redability. In the future we may want to mimick the c++ behavior
    # more closely, but this will make the code a lot more messy.
    def escape(c):
      o = ord(c)
      if o == 10: return r"\n"   # optional escape
      if o == 39: return r"\'"   # optional escape

      if o == 34: return r'\"'   # necessary escape
      if o == 92: return r"\\"   # necessary escape

      if o >= 127 or o < 32: return "\\%03o" % o # necessary escapes
      return c
    return '"' + "".join([escape(c) for c in value]) + '"'
  def DebugFormatFloat(self, value):
    return "%ff" % value
  def DebugFormatFixed32(self, value):
    if (value < 0): value += (1L<<32)
    return "0x%x" % value
  def DebugFormatFixed64(self, value):
    if (value < 0): value += (1L<<64)
    return "0x%x" % value
  def DebugFormatBool(self, value):
    if value:
      return "true"
    else:
      return "false"

# users of protocol buffers usually won't need to concern themselves
# with either Encoders or Decoders.
class Encoder:

  # types of data
  NUMERIC     = 0
  DOUBLE      = 1
  STRING      = 2
  STARTGROUP  = 3
  ENDGROUP    = 4
  FLOAT       = 5
  MAX_TYPE    = 6

  def __init__(self):
    self.buf = array.array('B')
    return

  def buffer(self):
    return self.buf

  def put8(self, v):
    if v < 0 or v >= (1<<8): raise ProtocolBufferEncodeError, "u8 too big"
    self.buf.append(v & 255)
    return

  def put16(self, v):
    if v < 0 or v >= (1<<16): raise ProtocolBufferEncodeError, "u16 too big"
    self.buf.append((v >> 0) & 255)
    self.buf.append((v >> 8) & 255)
    return

  def put32(self, v):
    if v < 0 or v >= (1L<<32): raise ProtocolBufferEncodeError, "u32 too big"
    self.buf.append((v >> 0) & 255)
    self.buf.append((v >> 8) & 255)
    self.buf.append((v >> 16) & 255)
    self.buf.append((v >> 24) & 255)
    return

  def put64(self, v):
    if v < 0 or v >= (1L<<64): raise ProtocolBufferEncodeError, "u64 too big"
    self.buf.append((v >> 0) & 255)
    self.buf.append((v >> 8) & 255)
    self.buf.append((v >> 16) & 255)
    self.buf.append((v >> 24) & 255)
    self.buf.append((v >> 32) & 255)
    self.buf.append((v >> 40) & 255)
    self.buf.append((v >> 48) & 255)
    self.buf.append((v >> 56) & 255)
    return

  def putVarInt32(self, v):
    if v >= (1L << 31) or v < -(1L << 31):
      raise ProtocolBufferEncodeError, "int32 too big"
    self.putVarInt64(v)
    return

  def putVarInt64(self, v):
    if v >= (1L << 63) or v < -(1L << 63):
      raise ProtocolBufferEncodeError, "int64 too big"
    if v < 0:
      v += (1L << 64)
    self.putVarUint64(v)
    return

  def putVarUint64(self, v):
    if v < 0 or v >= (1L << 64):
      raise ProtocolBufferEncodeError, "uint64 too big"
    while 1:
      bits = v & 127
      v >>= 7
      if (v != 0):
        bits |= 128
      self.buf.append(bits)
      if v == 0:
        break
    return


  # TODO: should we make sure that v actually has no more precision than
  #       float (so it comes out exactly as it goes in)?  Probably not -
  #       users expect their value to be rounded, and they would be
  #       annoyed if we forced them do it themselves.
  def putFloat(self, v):
    a = array.array('B')
    a.fromstring(struct.pack("f", v))
    self.buf.extend(a)
    return

  def putDouble(self, v):
    a = array.array('B')
    a.fromstring(struct.pack("d", v))
    self.buf.extend(a)
    return

  def putBoolean(self, v):
    if v:
      self.buf.append(1)
    else:
      self.buf.append(0)
    return

  def putPrefixedString(self, v):
    self.putVarInt32(len(v))
    a = array.array('B')
    a.fromstring(v)
    self.buf.extend(a)
    return

  def putRawString(self, v):
    a = array.array('B')
    a.fromstring(v)
    self.buf.extend(a)


class Decoder:
  def __init__(self, buf, idx, limit):
    self.buf = buf
    self.idx = idx
    self.limit = limit
    return

  def avail(self):
    return self.limit - self.idx

  def buffer(self):
    return self.buf

  def pos(self):
    return self.idx

  def skip(self, n):
    if self.idx + n > self.limit: raise ProtocolBufferDecodeError, "truncated"
    self.idx += n
    return

  def skipData(self, tag):
    t = tag & 7               # tag format type
    if t == Encoder.NUMERIC:
      self.getVarInt64()
    elif t == Encoder.DOUBLE:
      self.skip(8)
    elif t == Encoder.STRING:
      n = self.getVarInt32()
      self.skip(n)
    elif t == Encoder.STARTGROUP:
      while 1:
        t = self.getVarInt32()
        if (t & 7) == Encoder.ENDGROUP:
          break
        else:
          self.skipData(t)
      if (t - Encoder.ENDGROUP) != (tag - Encoder.STARTGROUP):
        raise ProtocolBufferDecodeError, "corrupted"
    elif t == Encoder.ENDGROUP:
      raise ProtocolBufferDecodeError, "corrupted"
    elif t == Encoder.FLOAT:
      self.skip(4)
    else:
      raise ProtocolBufferDecodeError, "corrupted"

  # these are all unsigned gets
  def get8(self):
    if self.idx >= self.limit: raise ProtocolBufferDecodeError, "truncated"
    c = self.buf[self.idx]
    self.idx += 1
    return c

  def get16(self):
    if self.idx + 2 > self.limit: raise ProtocolBufferDecodeError, "truncated"
    c = self.buf[self.idx]
    d = self.buf[self.idx + 1]
    self.idx += 2
    return (d << 8) | c

  def get32(self):
    if self.idx + 4 > self.limit: raise ProtocolBufferDecodeError, "truncated"
    c = self.buf[self.idx]
    d = self.buf[self.idx + 1]
    e = self.buf[self.idx + 2]
    f = long(self.buf[self.idx + 3])
    self.idx += 4
    return (f << 24) | (e << 16) | (d << 8) | c

  def get64(self):
    if self.idx + 8 > self.limit: raise ProtocolBufferDecodeError, "truncated"
    c = self.buf[self.idx]
    d = self.buf[self.idx + 1]
    e = self.buf[self.idx + 2]
    f = long(self.buf[self.idx + 3])
    g = long(self.buf[self.idx + 4])
    h = long(self.buf[self.idx + 5])
    i = long(self.buf[self.idx + 6])
    j = long(self.buf[self.idx + 7])
    self.idx += 8
    return ((j << 56) | (i << 48) | (h << 40) | (g << 32) | (f << 24)
            | (e << 16) | (d << 8) | c)

  def getVarInt32(self):
    v = self.getVarInt64()
    if v >= (1L << 31) or v < -(1L << 31):
      raise ProtocolBufferDecodeError, "corrupted"
    return v

  def getVarInt64(self):
    result = self.getVarUint64()
    if result >= (1L << 63):
      result -= (1L << 64)
    return result

  def getVarUint64(self):
    result = long(0)
    shift = 0
    while 1:
      if shift >= 64: raise ProtocolBufferDecodeError, "corrupted"
      b = self.get8()
      result |= (long(b & 127) << shift)
      shift += 7
      if (b & 128) == 0:
        if result >= (1L << 64): raise ProtocolBufferDecodeError, "corrupted"
        return result
    return result             # make pychecker happy

  def getFloat(self):
    if self.idx + 4 > self.limit: raise ProtocolBufferDecodeError, "truncated"
    a = self.buf[self.idx:self.idx+4]
    self.idx += 4
    return struct.unpack("f", a)[0]

  def getDouble(self):
    if self.idx + 8 > self.limit: raise ProtocolBufferDecodeError, "truncated"
    a = self.buf[self.idx:self.idx+8]
    self.idx += 8
    return struct.unpack("d", a)[0]

  def getBoolean(self):
    b = self.get8()
    if b != 0 and b != 1: raise ProtocolBufferDecodeError, "corrupted"
    return b

  def getPrefixedString(self):
    length = self.getVarInt32()
    if self.idx + length > self.limit:
      raise ProtocolBufferDecodeError, "truncated"
    r = self.buf[self.idx : self.idx + length]
    self.idx += length
    return r.tostring()

  def getRawString(self):
    r = self.buf[self.idx:self.limit]
    self.idx = self.limit
    return r.tostring()


class ProtocolBufferDecodeError(Exception): pass
class ProtocolBufferEncodeError(Exception): pass
class ProtocolBufferReturnError(Exception): pass