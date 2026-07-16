# When to Write C Extensions vs ctypes/cffi/Cython

## Concept

Python's interoperability with C covers a spectrum from zero-overhead native extensions to safe, high-level bindings. The right choice depends on ownership of the C code, performance requirements, and maintenance cost.

### Decision Matrix

| Need | Tool |
|------|------|
| Wrap an existing C library (no source changes) | `ctypes` (stdlib) or `cffi` |
| Wrap a C++ library | `pybind11` |
| Speed up Python code with C-speed loops | `Cython` |
| Maximum performance, full control | C API (`Python.h`) |
| Rust-based extension | `PyO3` |
| NumPy-integrated C extension | NumPy C API |
| Quick prototyping of FFI | `cffi` (easier than ctypes) |

### `ctypes` — Zero-Dependency FFI

```python
import ctypes
import ctypes.util

# Load a shared library:
libc = ctypes.CDLL(ctypes.util.find_library('c'))

# Call strlen:
libc.strlen.restype = ctypes.c_size_t
libc.strlen.argtypes = [ctypes.c_char_p]

result = libc.strlen(b"hello world")
print(result)   # 11

# Loading a custom library:
libmath = ctypes.CDLL('./libmath.so')  # or .dll on Windows

# Define function signature:
libmath.fast_sum.restype = ctypes.c_double
libmath.fast_sum.argtypes = [
    ctypes.POINTER(ctypes.c_double),  # double* array
    ctypes.c_int,                      # int n
]

# Call with numpy array:
import numpy as np
arr = np.array([1.0, 2.0, 3.0], dtype=np.float64)
result = libmath.fast_sum(
    arr.ctypes.data_as(ctypes.POINTER(ctypes.c_double)),
    len(arr)
)
```

### `cffi` — C Foreign Function Interface

```python
from cffi import FFI

ffi = FFI()

# Declare the C API:
ffi.cdef("""
    typedef struct {
        int x;
        int y;
    } Point;

    double distance(Point a, Point b);
    void process_array(double* data, int n);
""")

# Load the library:
lib = ffi.dlopen("./libgeometry.so")

# Use:
a = ffi.new("Point *", {'x': 0, 'y': 0})
b = ffi.new("Point *", {'x': 3, 'y': 4})
d = lib.distance(a[0], b[0])
print(d)   # 5.0

# Working with arrays:
import numpy as np
arr = np.array([1.0, 2.0, 3.0], dtype=np.float64)
lib.process_array(ffi.cast("double *", arr.ctypes.data), len(arr))
```

**cffi vs ctypes:**
- cffi: cleaner API, C header file approach, better for complex structs.
- ctypes: stdlib (no dependency), fine for simple function calls.

### Cython — Python to C Compiler

Cython compiles a Python-like language (`.pyx`) to C, then to a `.so`:

```cython
# fast_math.pyx
def sum_squares(list data):
    cdef double total = 0.0
    cdef double x
    for x in data:
        total += x * x
    return total

# Typed version — much faster:
def sum_squares_typed(double[:] data):
    """Accepts numpy array of float64."""
    cdef int n = data.shape[0]
    cdef double total = 0.0
    cdef int i
    for i in range(n):
        total += data[i] * data[i]
    return total
```

```python
# setup.py for Cython:
from setuptools import setup
from Cython.Build import cythonize
import numpy as np

setup(
    ext_modules=cythonize("fast_math.pyx", annotate=True),
    include_dirs=[np.get_include()],
)
# Build: python setup.py build_ext --inplace
# Creates: fast_math.so

import fast_math
import numpy as np
arr = np.arange(1000, dtype=np.float64)
fast_math.sum_squares_typed(arr)  # ~100x faster than pure Python
```

### `pybind11` — C++ Bindings

```cpp
// module.cpp
#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
#include <vector>

namespace py = pybind11;

double fast_sum(const std::vector<double>& v) {
    double total = 0;
    for (auto x : v) total += x;
    return total;
}

PYBIND11_MODULE(mymodule, m) {
    m.doc() = "Fast math operations";
    m.def("fast_sum", &fast_sum, "Sum a list of floats");
}
```

```toml
# pyproject.toml:
[build-system]
requires = ["pybind11", "setuptools"]
build-backend = "setuptools.build_meta"
```

### PyO3 — Rust Extensions

```rust
// src/lib.rs
use pyo3::prelude::*;

#[pyfunction]
fn fast_sum(v: Vec<f64>) -> f64 {
    v.iter().sum()
}

#[pymodule]
fn mymodule(_py: Python, m: &PyModule) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(fast_sum, m)?)?;
    Ok(())
}
```

```bash
# Using maturin:
pip install maturin
maturin develop   # build and install in current venv
# or: maturin build --release  # build wheel
```

---

## Interview Questions

### Q1: When is `ctypes` sufficient and when should you upgrade to `cffi` or a native extension?

**Model answer:**
`ctypes` is sufficient for:
- Calling a few C library functions with simple types (int, double, char*, struct pointers).
- Quick prototyping or one-off scripts.
- No need for error handling, callbacks, or complex structs.

Upgrade to `cffi` when:
- You have a C header file you can paste directly (`ffi.cdef()`).
- You need more complex types (nested structs, arrays, function pointers for callbacks).
- You want ABI-level compatibility checking.

Upgrade to a native extension (`pybind11`, C API, Cython) when:
- **Performance is critical:** ctypes/cffi add per-call overhead (~microseconds) — unacceptable if calling C code millions of times.
- **GIL release needed:** only native extensions can properly release the GIL and release it for the duration of C computation.
- **NumPy integration:** buffer protocol access requires native extension or Cython typed memoryviews.
- **Bidirectional callbacks:** C calling back into Python at high frequency is painful in ctypes.

### Q2: What is Cython's `cdef` and how does it achieve C-level speed?

**Model answer:**
`cdef` declares a C-typed variable or function. Cython generates C code that uses these C types directly — no Python object boxing/unboxing overhead in the hot path:

```cython
# Pure Python: each iteration creates Python int objects
def slow_sum(n: int) -> int:
    total = 0
    for i in range(n):
        total += i  # Python int operations: boxing, unboxing, refcount
    return total

# Cython with cdef: C-speed integers
def fast_sum(int n) -> long long:
    cdef long long total = 0
    cdef int i
    for i in range(n):
        total += i  # pure C addition: no Python objects
    return total
```

The `annotate=True` flag in `cythonize()` generates an HTML file coloring lines yellow (Python overhead) to white (pure C). Yellow lines are optimization targets.

Key Cython optimizations:
- `cdef int i` → C `int` variable, not Python `int`
- `double[:]` memoryview → direct C array access, no bounds checking when `@cython.boundscheck(False)`
- `cython.wraparound(False)` → remove negative index support
- `nogil` → release GIL for parallel execution

### Q3: What's the difference between `ctypes.CDLL`, `ctypes.WinDLL`, and `ctypes.PyDLL`?

**Model answer:**
All three load shared libraries, but differ in GIL handling and calling convention:

- `CDLL`: cdecl calling convention (Linux/macOS default). Releases the GIL before each call (via `Py_BEGIN_ALLOW_THREADS`), re-acquires after.
- `WinDLL`: stdcall calling convention (Windows APIs like Win32). Also releases GIL.
- `PyDLL`: does NOT release the GIL. Use only for functions that access Python C API objects (need the GIL held). Releasing the GIL when calling Python API functions causes crashes.

```python
import ctypes

# Calling a pure C function: CDLL releases GIL → other threads can run
libc = ctypes.CDLL("libc.so.6")
libc.sleep(1)   # GIL released — other Python threads continue running

# If you wrote a C function that calls PyObject_* functions:
# Use PyDLL — GIL must stay held:
mylib = ctypes.PyDLL("./mylib.so")
mylib.python_callback_fn(...)  # GIL held throughout
```

### Q4: When would you choose Rust/PyO3 over C/pybind11 for a Python extension?

**Model answer:**
Choose **Rust/PyO3** when:
- **Memory safety:** Rust's borrow checker prevents buffer overflows, use-after-free, data races — without GC overhead.
- **Modern tooling:** `maturin` makes build/publish trivial; Rust's package manager (Cargo) is excellent.
- **Concurrency without GIL:** Rust threads don't share Python objects and can parallelize freely.
- **Team comfort:** Rust is increasingly popular; easier to hire than C++ with pybind11.

Choose **C++/pybind11** when:
- You have existing C++ code to wrap (lower rewrite cost).
- The team already knows C++.
- You need features pybind11 handles well (STL containers, smart pointers).

Choose **C API** when:
- Maximum control over CPython object lifecycle.
- Wrapping CPython internals or implementing a new built-in type.
- No C++ or Rust dependency is acceptable.

Most greenfield extension work today defaults to PyO3 (safety) or pybind11 (C++ integration), not raw C API.

### Q5: How do you safely pass a numpy array to a C function via ctypes?

**Model answer:**
Numpy arrays expose a `ctypes` attribute for safe pointer passing:

```python
import numpy as np
import ctypes

libmath = ctypes.CDLL("./libmath.so")
libmath.process.argtypes = [
    ctypes.POINTER(ctypes.c_double),
    ctypes.c_int,
    ctypes.c_int,
]
libmath.process.restype = ctypes.c_double

arr = np.array([1.0, 2.0, 3.0, 4.0], dtype=np.float64)

# CORRECT: use ctypes.data_as for type-safe pointer:
result = libmath.process(
    arr.ctypes.data_as(ctypes.POINTER(ctypes.c_double)),
    ctypes.c_int(len(arr)),
    ctypes.c_int(arr.strides[0] // arr.itemsize),
)

# WRONG: passing arr.ctypes.data directly (void*, loses type info):
# libmath.process(arr.ctypes.data, ...)  # may work but type-unsafe

# Ensure contiguity before passing:
arr = np.ascontiguousarray(arr, dtype=np.float64)  # C-contiguous, float64

# For 2D arrays:
arr_2d = np.ascontiguousarray(matrix, dtype=np.float64)
ptr = arr_2d.ctypes.data_as(ctypes.POINTER(ctypes.c_double))
rows, cols = arr_2d.shape
```

Critical: ensure the array is contiguous (`np.ascontiguousarray`) and the correct dtype before passing — C functions expect a flat memory layout.

---

## Gotcha Follow-ups

**"What happens if a ctypes-called function raises a signal or calls `exit()`?"**
`exit()` in C terminates the entire Python process without running Python cleanup, `__del__`, or `atexit` handlers. `signal()` from C bypasses Python's signal handling. For signal safety: always use `sigaction` in C extensions and check `PyErr_CheckSignals()` periodically in long-running C code.

**"Can Cython release the GIL?"**
Yes — `with nogil:` in Cython releases the GIL for the duration of the block. The block must contain only C code (no Python objects, no Python API calls). This enables true parallelism:
```cython
from cython.parallel import prange

def parallel_sum(double[:] arr) -> double:
    cdef double total = 0.0
    cdef int i
    with nogil:
        for i in prange(arr.shape[0]):  # OpenMP parallel loop
            total += arr[i]
    return total
```

---

## Under the Hood

`ctypes` uses `libffi` (a portable FFI library) internally. `libffi` handles platform-specific calling conventions (argument passing in registers vs stack, return value handling) transparently. When ctypes calls a function, it: (1) releases the GIL via `Py_BEGIN_ALLOW_THREADS`, (2) invokes `libffi.call()` with prepared argument buffers, (3) re-acquires the GIL via `Py_END_ALLOW_THREADS`, (4) converts the return value to a Python object. This GIL release/acquire on every call is the overhead that makes ctypes/cffi slower than native extensions for high-frequency calls.
