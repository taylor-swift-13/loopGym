// Source: data/benchmarks/sv-benchmarks/loop-acceleration/multivar_1-1.c
extern unsigned int unknown_uint(void);

void loopy_341(unsigned int x) {
  
  unsigned int y = x;

  while (x < 1024) {
    x++;
    y++;
  }

  {;
//@ assert(x == y);
}

}