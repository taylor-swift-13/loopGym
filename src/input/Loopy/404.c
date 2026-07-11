// Source: data/benchmarks/sv-benchmarks/loop-zilu/benchmark17_conjunctive.c
extern int unknown_int(void);
/*@
  requires i==0 && k==0;
*/
void loopy_404(int i, int k, int n) {
  
  
  
  
  
  while (i<n) {
    i++;
    k++;
  }
  {;
//@ assert(k>=n);
}

  return;
}