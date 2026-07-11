// Source: data/benchmarks/sv-benchmarks/loop-invariants/even.c
extern int unknown_int(void);

void loopy_361(void) {
  unsigned int x = 0;
  while (unknown_int()) {
    x += 2;
  }
  {;
//@ assert(!(x % 2));
}

  return;
}