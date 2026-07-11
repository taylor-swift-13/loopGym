// Source: data/benchmarks/sv-benchmarks/loop-zilu/benchmark43_conjunctive.c
extern int unknown_int(void);
/*@
  requires x < 100 && y < 100;
*/
void loopy_429(int x, int y) {
  
  
  
  while (x < 100 && y < 100) {
    x=x+1;
    y=y+1;
  }
  {;
//@ assert(x == 100 || y == 100);
}

  return;
}