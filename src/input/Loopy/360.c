// Source: data/benchmarks/sv-benchmarks/loop-invariants/eq2.c
extern unsigned int unknown_uint(void);

void loopy_360(unsigned int w) {
  
  unsigned int x = w;
  unsigned int y = w + 1;
  unsigned int z = x + 1;
  while (unknown_uint()) {
    y++;
    z++;
  }
  {;
//@ assert(y == z);
}

  return;
}