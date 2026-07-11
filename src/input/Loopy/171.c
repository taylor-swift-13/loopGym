// Source: data/benchmarks/accelerating_invariant_generation/crafted/underapprox_safe2.c

void loopy_171(void) {
  unsigned int x = 0;
  unsigned int y = 1;

  while (x < 6) {
    x++;
    y *= 2;
  }

  {;
//@ assert(x == 6);
}

}