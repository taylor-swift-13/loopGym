// Source: data/benchmarks/sv-benchmarks/loop-acceleration/underapprox_1-2.c

void loopy_349(void) {
  unsigned int x = 0;
  unsigned int y = 1;

  while (x < 6) {
    x++;
    y *= 2;
  }

  {;
//@ assert(y % 3);
}

}