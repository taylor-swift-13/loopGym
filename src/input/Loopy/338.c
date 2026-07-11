// Source: data/benchmarks/sv-benchmarks/loop-acceleration/const_1-1.c

void loopy_338(void) {
  unsigned int x = 1;
  unsigned int y = 0;

  while (y < 1024) {
    x = 0;
    y++;
  }

  {;
//@ assert(x == 0);
}

}