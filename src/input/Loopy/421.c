// Source: data/benchmarks/sv-benchmarks/loop-zilu/benchmark35_linear.c
extern int unknown_int(void);
/*@
  requires x>=0;
*/
void loopy_421(int x) {
  
  
  while ((x>=0) && (x<10)) {
    x=x+1;
  }
  {;
//@ assert(x>=10);
}

  return;
}