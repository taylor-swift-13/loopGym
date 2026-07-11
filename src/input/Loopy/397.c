// Source: data/benchmarks/sv-benchmarks/loop-zilu/benchmark10_conjunctive.c
extern int unknown_int(void);
/*@
  requires c==0 && i==0;
*/
void loopy_397(int i, int c) {
  
  
  
  
  while (i<100) {
    c=c+i;
    i=i+1;
    if (i<=0) break;
  }
  {;
//@ assert(c>=0);
}

  return;
}