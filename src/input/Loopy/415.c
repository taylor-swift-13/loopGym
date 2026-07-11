// Source: data/benchmarks/sv-benchmarks/loop-zilu/benchmark29_linear.c
extern int unknown_int(void);
/*@
  requires x<y;
*/
void loopy_415(int x, int y) {
  
  
  
  while (x<y) {
    x=x+100;
  }
  {;
//@ assert(x >= y && x <= y + 99);
}

  return;
}