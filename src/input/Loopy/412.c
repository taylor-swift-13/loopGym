// Source: data/benchmarks/sv-benchmarks/loop-zilu/benchmark25_linear.c
extern int unknown_int(void);
/*@
  requires x<0;
*/
void loopy_412(int x) {
  
  
  while (x<10) {
    x=x+1;
  }
  {;
//@ assert(x==10);
}

  return;
}