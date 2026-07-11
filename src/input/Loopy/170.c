// Source: data/benchmarks/accelerating_invariant_generation/crafted/simple_safe4.c

void loopy_170(void) {
  unsigned int x = 0x0ffffff0;

  while (x > 0) {
    x -= 2;
  }

  {;
//@ assert(!(x % 2));
}

}