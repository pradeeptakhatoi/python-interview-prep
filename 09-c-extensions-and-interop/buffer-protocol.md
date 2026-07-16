# The Buffer Protocol and memoryview

## Concept

The buffer protocol is CPython's mechanism for sharing memory between objects without copying. Objects that implement the buffer protocol expose a contiguous (or strided) region of memory that other objects can read or write directly.

### The Protocol

Any Python object can implement the buffer protocol by implementing `PyObject_GetBuffer()` in C (or `__buffer__` in Python 3.12+). Objects that do so include: `bytes`, `bytearray`, `array.array`, `numpy.ndarray`, and most binary I/O objects.

```python
# Objects that support the buffer protocol:
b = b"hello"               # bytes: read-only buffer
ba = bytearray(b"hello")   # bytearray: writable buffer
import array
arr = array.array('d', [1.0, 2.0, 3.0])  # array: typed buffer
import numpy as np
np_arr = np.zeros((3, 3), dtype=np.float64)  # numpy: strided buffer

# memoryview exposes the buffer protocol to Python:
mv = memoryview(b)
print(mv[0])    # 104 (ASCII 'h')
print(bytes(mv[1:3]))  # b"el"
print(mv.nbytes)    # 5
print(mv.format)    # 'B' (unsigned byte)
print(mv.readonly)  # True (bytes is immutable)
```

### `memoryview` — Zero-Copy Slicing

```python
import struct

data = bytearray(b'\x00\x01\x02\x03\x04\x05\x06\x07')
mv = memoryview(data)

# Slicing creates a VIEW — no copy:
slice1 = mv[2:6]   # view of bytes 2-5
print(bytes(slice1))   # b'\x02\x03\x04\x05'

# Modifying the slice modifies the underlying data:
slice1[0] = 99
print(data[2])    # 99 — data modified through the view!

# Cast to different type (reinterpret memory):
mv_int = mv.cast('H')   # reinterpret as unsigned short (2 bytes each)
print(list(mv_int))     # [256, 770, 1284, 99|5<<8] — two bytes per int
print(mv_int.itemsize)  # 2

# Cast to numpy-compatible format:
import numpy as np
np_view = np.asarray(mv.cast('d'))   # reinterpret as float64 — zero copy!
```

### Buffer Protocol in Network I/O

The buffer protocol enables zero-copy I/O — passing memory directly to OS system calls:

```python
import socket

# Sending data without copy:
data = bytearray(1024 * 1024)  # 1 MB buffer
mv = memoryview(data)

sock = socket.socket()
sock.connect(('localhost', 8080))

# Send in chunks without copying:
offset = 0
while offset < len(data):
    # sock.send() accepts the buffer protocol — no copy to internal buffer
    sent = sock.send(mv[offset:offset + 65536])
    offset += sent

# Receiving into pre-allocated buffer:
recv_buf = bytearray(4096)
while True:
    # recv_into() writes directly into recv_buf — no intermediate copy:
    n = sock.recv_into(mv := memoryview(recv_buf), 4096)
    if not n:
        break
    process(recv_buf[:n])
```

### Typed Memoryviews in Cython

```cython
# Cython: typed memoryview for direct C array access
import numpy as np

def process_matrix(double[:, :] matrix):
    """
    Accept any 2D float64 buffer (numpy, array.array, etc.)
    Access without Python overhead.
    """
    cdef int rows = matrix.shape[0]
    cdef int cols = matrix.shape[1]
    cdef double total = 0.0
    cdef int i, j

    for i in range(rows):
        for j in range(cols):
            total += matrix[i, j]   # direct C array access, no Python

    return total

# Call with numpy array:
mat = np.ones((1000, 1000), dtype=np.float64)
result = process_matrix(mat)
```

### `struct` Module — Binary Format Parsing

```python
import struct

# Parse a binary protocol header (no copy):
header_data = b'\x01\x00\x00\x00\x00\x00\x10\x00ABC'
version, flags, length = struct.unpack_from('>BHI', header_data)
# > = big-endian, B = uint8, H = uint16, I = uint32

# Pack to binary:
packet = struct.pack('>BHI', 1, 0, 4096) + b'DATA'

# Use with memoryview for zero-copy parsing of large buffers:
large_buf = bytearray(10_000)
mv = memoryview(large_buf)
# Parse 100 records of 100 bytes each:
RECORD_FMT = '>IIBD'  # two uint32, uint8, float64
RECORD_SIZE = struct.calcsize(RECORD_FMT)
records = [
    struct.unpack_from(RECORD_FMT, mv, offset=i * RECORD_SIZE)
    for i in range(len(large_buf) // RECORD_SIZE)
]
```

---

## Interview Questions

### Q1: What is the buffer protocol and why does it matter for performance?

**Model answer:**
The buffer protocol is a C-level interface that allows Python objects to expose their underlying memory to other Python code without copying. Any object implementing `PyBUF_SIMPLE` or `PyBUF_WRITABLE` in C can participate.

Performance impact: copying large data buffers is O(n) in time and memory. The buffer protocol makes this O(1) — sharing the same memory region.

```python
import numpy as np

arr = np.zeros(10_000_000, dtype=np.float64)   # 80 MB

# WITHOUT buffer protocol: socket.send would copy 80 MB
# WITH buffer protocol:
import socket
sock = socket.socket()
sock.connect(('localhost', 8080))
sock.sendall(arr)   # numpy array directly supported — no copy!
# kernel reads from arr's memory directly via sendfile/writev

# Same for file I/O:
with open('/tmp/data.bin', 'wb') as f:
    f.write(arr)   # no copy — fwrite reads from arr's buffer

# memoryview makes this explicit:
mv = memoryview(arr.tobytes())  # THIS copies (bytes is a new allocation)
mv2 = memoryview(arr)           # THIS does NOT copy (numpy supports buffer protocol)
```

### Q2: How does `memoryview` slicing differ from `bytes` slicing?

**Model answer:**
`bytes` slicing creates a NEW bytes object (copies the data). `memoryview` slicing creates a new view into the same underlying memory — O(1) regardless of slice size:

```python
import sys

data = b'x' * 1_000_000   # 1 MB bytes object

# bytes slicing: COPIES
slice_bytes = data[100:200]   # allocates new bytes object with 100 bytes
print(sys.getsizeof(slice_bytes))  # 137 bytes (100 bytes + overhead)

# memoryview slicing: NO COPY
mv = memoryview(data)
slice_mv = mv[100:200]   # just adjusts pointer and length
print(sys.getsizeof(slice_mv))   # 200 bytes (memoryview object overhead, no data copy)
print(id(slice_mv.obj) == id(mv.obj))  # True — same underlying object!

# Practical: parse a large binary packet without copying:
def parse_header(buf: memoryview) -> tuple:
    return buf[0], int.from_bytes(buf[1:5], 'big')

packet = bytearray(1000)
mv = memoryview(packet)
parse_header(mv[:10])   # zero-copy header parsing
parse_header(mv[10:20]) # zero-copy next segment
```

For large data processing (video frames, binary protocols, network data), using `memoryview` throughout the processing pipeline eliminates copies at each step.

### Q3: What does `memoryview.cast()` do and when would you use it?

**Model answer:**
`cast(format)` reinterprets the underlying bytes as a different type — like C's `(type*)` cast, but checked:

```python
import struct

raw = bytearray(struct.pack('4f', 1.0, 2.0, 3.0, 4.0))   # 16 bytes
mv = memoryview(raw)

print(mv.format)  # 'B' — unsigned bytes
print(list(mv[:4]))  # raw bytes: [0, 0, 128, 63] (IEEE 754 for 1.0)

# Cast to float:
mv_float = mv.cast('f')   # reinterpret as 4-byte floats
print(list(mv_float))     # [1.0, 2.0, 3.0, 4.0] — no copy!

# Cast to 2D:
mv_2d = mv_float.cast('f', shape=[2, 2])
print(mv_2d[0, 0])  # 1.0
print(mv_2d[1, 1])  # 4.0
```

Use cases:
- Parsing binary protocols: `struct.pack` creates bytes; cast to interpret as float/int array.
- Feeding data to numpy without copy: `np.asarray(mv.cast('d'))` for float64.
- Processing audio/video frames: reinterpret raw bytes as int16 or float32 samples.

### Q4: How would you implement a zero-copy file-to-socket transfer in Python?

**Model answer:**

```python
import socket, os

# Option 1: sendfile — OS-level zero copy (page cache to NIC, no userspace copy)
def send_file_zero_copy(sock: socket.socket, path: str) -> int:
    file_size = os.path.getsize(path)
    with open(path, 'rb') as f:
        # socket.sendfile() uses sendfile(2) on Linux/macOS:
        return sock.sendfile(f, count=file_size)

# Option 2: mmap + memoryview (userspace zero-copy)
import mmap

def send_large_file(sock: socket.socket, path: str) -> None:
    with open(path, 'rb') as f:
        with mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ) as mm:
            mv = memoryview(mm)
            offset = 0
            while offset < len(mm):
                chunk = mv[offset:offset + 65536]
                sent = sock.send(chunk)   # no copy — memoryview to socket
                offset += sent

# Option 3: splice (Linux only, truly zero-copy kernel to kernel)
# Available via ctypes or cffi calling splice(2) syscall directly
```

`socket.sendfile()` is the right answer for file-to-socket — it uses the OS `sendfile` syscall which transfers data from the file's page cache directly to the network buffer without copying through userspace.

### Q5: What is a strided buffer and how does numpy use it?

**Model answer:**
A strided buffer is a buffer where elements are not necessarily contiguous — each element is accessed by a fixed number of bytes (the stride) from the previous:

```python
import numpy as np

# 2D array:
arr = np.arange(12, dtype=np.float64).reshape(3, 4)
print(arr.strides)   # (32, 8) — 32 bytes between rows, 8 bytes between cols

# Transpose doesn't copy — just changes strides:
t = arr.T
print(t.strides)   # (8, 32) — swapped strides, same memory!
print(np.shares_memory(arr, t))  # True

# Column slice — strided, no copy:
col = arr[:, 1]   # every 4th element (stride=32 bytes)
print(col.strides)   # (32,) — still strided
print(np.shares_memory(arr, col))   # True

# Accessing strided arrays via memoryview:
mv = memoryview(arr)
print(mv.strides)   # (32, 8) — matches numpy strides
print(mv.contiguous)  # True (C-order contiguous)

# Transposed view is NOT C-contiguous:
mv_t = memoryview(np.ascontiguousarray(t))  # must copy to get C-contiguous
print(mv_t.contiguous)   # True (now contiguous)
```

C functions typically require C-contiguous data (no gaps). Before passing a strided numpy array to ctypes, call `np.ascontiguousarray(arr)` to ensure contiguous layout. This copies only if needed.

---

## Gotcha Follow-ups

**"Does `memoryview` prevent garbage collection of the underlying object?"**
Yes — a `memoryview` holds a strong reference to its `obj` (the underlying buffer owner). The buffer owner is NOT garbage-collected while any `memoryview` pointing to it is alive. This is the correct behavior — the C memory must not be freed while something holds a pointer to it. Always release `memoryview` objects when done (or use `with` blocks for explicit release).

**"Can you create a buffer protocol object in pure Python?"**
Python 3.12+ adds `__buffer__` and `__release_buffer__` dunder methods for pure Python buffer support (PEP 688). Before 3.12, you had to write a C extension or use numpy. Post-3.12 example: `class MyBuffer: def __buffer__(self, flags): return memoryview(self._data).__buffer__(flags)`.

---

## Under the Hood

`PyObject_GetBuffer()` (`Objects/abstract.c`): calls `tp_as_buffer->bf_getbuffer(obj, &view, flags)` where `view` is a `Py_buffer` struct containing: `buf` (C pointer), `len` (byte count), `itemsize`, `format` (struct format string), `ndim`, `shape`, `strides`, `suboffsets`. `memoryview` wraps a `Py_buffer` and implements the buffer protocol itself (so you can take a memoryview of a memoryview). `socket.send()`, `f.write()`, `struct.pack_into()`, and many other stdlib functions accept any buffer-protocol object via `PyArg_ParseTuple("y*", &view)` — the `y*` format code.
