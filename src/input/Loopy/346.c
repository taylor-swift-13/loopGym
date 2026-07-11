// Source: data/benchmarks/sv-benchmarks/loop-acceleration/simple_2-1.c
extern unsigned int unknown_uint(void);

void loopy_346(unsigned int x) {
  

  while (x < 0x0fffffff) {
    x++;
  }

  {;
//@ assert(x >= 0x0fffffff);
}

}