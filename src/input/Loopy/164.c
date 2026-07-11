// Source: data/benchmarks/accelerating_invariant_generation/crafted/multivar_safe1.c

void loopy_164(unsigned int x) {
  
  unsigned int y = x;

  while (x < 100) {
    x++;
    y++;
  }

  {;
//@ assert(x == y);
}

}