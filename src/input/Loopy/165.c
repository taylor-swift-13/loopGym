// Source: data/benchmarks/accelerating_invariant_generation/crafted/overflow_safe1.c

void loopy_165(void) {
  unsigned int x = 10;

  while (x >= 10) {
    x += 2;
  }

  {;
//@ assert(!(x % 2));
}

}