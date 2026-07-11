// Source: data/benchmarks/sv-benchmarks/loop-invariants/bin-suffix-5.c
extern int unknown_int(void);

void loopy_357(void) {
  unsigned int x = 5;
  while (unknown_int()) {
    x += 8;
  }
  {;
//@ assert((x & 5) == 5);
}

  return;
}