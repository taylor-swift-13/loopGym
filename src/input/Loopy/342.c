// Source: data/benchmarks/sv-benchmarks/loop-acceleration/overflow_1-1.c

void loopy_342(void) {
  unsigned int x = 10;

  while (x >= 10) {
    x += 2;
  }

  {;
//@ assert(!(x % 2));
}

}