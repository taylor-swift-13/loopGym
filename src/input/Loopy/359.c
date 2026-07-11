// Source: data/benchmarks/sv-benchmarks/loop-invariants/eq1.c
extern unsigned int unknown_uint(void);

void loopy_359(unsigned int w, unsigned int y) {
  
  unsigned int x = w;
  
  unsigned int z = y;
  while (unknown_uint()) {
    if (unknown_uint()) {
      ++w; ++x;
    } else {
      --y; --z;
    }
  }
  {;
//@ assert(w == x && y == z);
}

  return;
}