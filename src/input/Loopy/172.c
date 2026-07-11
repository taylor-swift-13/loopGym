// Source: data/benchmarks/accelerating_invariant_generation/crafted/underapprox_unsafe1.c

void loopy_172(void) {
  unsigned int x = 0;
  unsigned int y = 1;

  while (x < 6) {
    x++;
    y *= 2;
  }

  {;
//@ assert(y != 12);
}

}