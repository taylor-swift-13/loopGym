// Source: data/benchmarks/accelerating_invariant_generation/crafted/const_safe1.c

void loopy_161(void) {
  unsigned int x = 1;
  unsigned int y = 0;

  while (y < 10) {
    x = 0;
    y++;
  }

  {;
//@ assert(x == 0);
}

}