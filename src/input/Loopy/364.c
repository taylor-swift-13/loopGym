// Source: data/benchmarks/sv-benchmarks/loop-invariants/odd.c
extern int unknown_int(void);

void loopy_364(void) {
  unsigned int x = 1;
  while (unknown_int()) {
    x += 2;
  }
  {;
//@ assert(x % 2);
}

  return;
}