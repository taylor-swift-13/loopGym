// Source: data/benchmarks/accelerating_invariant_generation/crafted/phases_safe1.c

void loopy_166(void) {
  unsigned int x = 0;

  while (x < 0x0fffffff) {
    if (x < 0xfff0) {
      x++;
    } else {
      x += 2;
    }
  }

  {;
//@ assert(!(x % 2));
}

}