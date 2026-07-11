// Source: data/benchmarks/sv-benchmarks/loop-acceleration/diamond_1-1.c
extern unsigned int unknown_uint(void);

void loopy_339(unsigned int y) {
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