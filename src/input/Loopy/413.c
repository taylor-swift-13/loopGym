// Source: data/benchmarks/sv-benchmarks/loop-zilu/benchmark26_linear.c
extern int unknown_int(void);
/*@
  requires x<y;
*/
void loopy_413(int x, int y) {
  
  
  
  while (x<y) {
    x=x+1;
  }
  {;
//@ assert(x==y);
}

  return;
}