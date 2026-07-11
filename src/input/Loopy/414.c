// Source: data/benchmarks/sv-benchmarks/loop-zilu/benchmark27_linear.c
extern int unknown_int(void);
/*@
  requires i<j && k>i-j;
*/
void loopy_414(int i, int j, int k) {
  
  
  
  
  while (i<j) {
    k=k+1;
    i=i+1;
  }
  {;
//@ assert(k > 0);
}

  return;
}