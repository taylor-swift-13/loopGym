// Source: data/benchmarks/accelerating_invariant_generation/crafted/simple_safe1.c

void loopy_167(void) {
  unsigned int x = 0;

  while (x < 0x0fffffff) {
    x += 2;
  }

  {;
//@ assert(!(x % 2));
}

}