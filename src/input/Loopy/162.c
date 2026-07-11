// Source: data/benchmarks/accelerating_invariant_generation/crafted/diamond_safe1.c

void loopy_162(unsigned int y) {
  unsigned int x = 0;
  

  while (x < 99) {
    if (y % 2 == 0) {
      x += 2;
    } else {
      x++;
    }
  }

  {;
//@ assert((x % 2) == (y % 2));
}

}