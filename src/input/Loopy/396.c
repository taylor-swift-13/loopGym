// Source: data/benchmarks/sv-benchmarks/loop-zilu/benchmark09_conjunctive.c
extern int unknown_int(void);
/*@
  requires x == y && y >=0;
*/
void loopy_396(int x, int y) {
  
  
  
  
  while (x!=0) {
    x--;
    y--;
    if (x<0 || y<0) break;
  }
  {;
//@ assert(y==0);
}

  return;
}