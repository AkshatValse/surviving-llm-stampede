"""Prefix-cache metastability pilot: iteration-level continuous-batching simulator."""
import os as _os

# The simulator is single-threaded Python; stop BLAS/OpenMP thread pools (they otherwise spin up
# one thread per core at numpy import, which breaks the "few CPU processes" rule on a shared machine).
for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "VECLIB_MAXIMUM_THREADS",
           "NUMEXPR_NUM_THREADS"):
    _os.environ.setdefault(_v, "1")
