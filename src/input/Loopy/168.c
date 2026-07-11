// Source: data/benchmarks/accelerating_invariant_generation/crafted/simple_safe2.c

void loopy_168(unsigned int x) {
  

  while (x < 0x0fffffff) {
    x++;
  }

  {;
//@ assert(x >= 0x0fffffff);
}

}