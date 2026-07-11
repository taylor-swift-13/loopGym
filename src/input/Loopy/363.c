// Source: data/benchmarks/sv-benchmarks/loop-invariants/mod4.c
extern int unknown_int(void);

void loopy_363(void) {
  unsigned int x = 0;
  while (unknown_int()) {
    x += 4;
  }
  {;
//@ assert(!(x % 4));
}

  return;
}