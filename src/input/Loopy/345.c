// Source: data/benchmarks/sv-benchmarks/loop-acceleration/simple_1-2.c

void loopy_345(void) {
  unsigned int x = 0;

  while (x < 0x0fffffff) {
    x += 2;
  }

  {;
//@ assert(!(x % 2));
}

}