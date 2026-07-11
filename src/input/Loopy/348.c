// Source: data/benchmarks/sv-benchmarks/loop-acceleration/simple_4-2.c

void loopy_348(void) {
  unsigned int x = 0x0ffffff0;

  while (x > 0) {
    x -= 2;
  }

  {;
//@ assert(!(x % 2));
}

}