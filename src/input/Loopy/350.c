// Source: data/benchmarks/sv-benchmarks/loop-acceleration/underapprox_2-2.c

void loopy_350(void) {
  unsigned int x = 0;
  unsigned int y = 1;

  while (x < 6) {
    x++;
    y *= 2;
  }

  {;
//@ assert(x == 6);
}

}