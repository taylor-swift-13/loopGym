// Source: data/benchmarks/sv-benchmarks/loop-zilu/benchmark42_conjunctive.c
extern int unknown_int(void);
/*@
  requires x == y && x >= 0 && x+y+z==0;
*/
void loopy_428(int x, int y, int z) {
  
  
  
  
  while (x > 0) {
    x--;
    y--;
    z++;
    z++;
  }
  {;
//@ assert(z<=0);
}

  return;
}