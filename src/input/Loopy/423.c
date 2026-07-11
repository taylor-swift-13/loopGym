// Source: data/benchmarks/sv-benchmarks/loop-zilu/benchmark37_conjunctive.c
extern int unknown_int(void);
/*@
  requires x == y && x >= 0;
*/
void loopy_423(int x, int y) {
  
  
  
  while (x > 0) {
    x--;
    y--;
  }
  {;
//@ assert(y>=0);
}

  return;
}