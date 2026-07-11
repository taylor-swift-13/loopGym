// Source: data/benchmarks/sv-benchmarks/loop-zilu/benchmark24_conjunctive.c
extern int unknown_int(void);
/*@
  requires i==0 && k==n && n>=0;
*/
void loopy_411(int i, int k, int n) {
  
  
  
  
  
  while (i<n) {
    k--;
    i+=2;
  }
  {;
//@ assert(2*k>=n-1);
}

  return;
}