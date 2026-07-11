// Source: data/benchmarks/sv-benchmarks/loop-zilu/benchmark39_conjunctive.c
extern int unknown_int(void);
/*@
  requires x == 4*y && x >= 0;
*/
void loopy_425(int x, int y) {
  
  
  
  while (x > 0) {
    x-=4;
    y--;
  }
  {;
//@ assert(y>=0);
}

  return;
}