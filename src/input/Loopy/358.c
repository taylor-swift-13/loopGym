// Source: data/benchmarks/sv-benchmarks/loop-invariants/const.c
extern unsigned int unknown_uint(void);

void loopy_358(void) {
  unsigned int s = 0;
  while (unknown_uint()) {
    if (s != 0) {
      ++s;
    }
    if (unknown_uint()) {
      {;
//@ assert(s == 0);
}

    }
  }
  return;
}