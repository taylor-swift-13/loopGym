// Source: data/benchmarks/sv-benchmarks/loop-zilu/benchmark33_linear.c
extern int unknown_int(void);
/*@
  requires x>=0;
*/
void loopy_419(int x) {
  
  
  
  while (x<100 && x>=0) {
    x++;
  }
  {;
//@ assert(x>=100);
}

  return;
}