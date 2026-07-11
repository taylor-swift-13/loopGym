// Source: data/benchmarks/sv-benchmarks/loop-zilu/benchmark04_conjunctive.c
extern int unknown_int(void);
/*@
  requires n>=1 && k>=n && j==0;
*/
void loopy_392(int k, int j, int n) {
  
  
  
  
  
  while (j<=n-1) {
    j++;
    k--;
  }
  {;
//@ assert(k>=0);
}

  return;
}