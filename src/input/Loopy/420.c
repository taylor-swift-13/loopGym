// Source: data/benchmarks/sv-benchmarks/loop-zilu/benchmark34_conjunctive.c
extern int unknown_int(void);
/*@
  requires (j==0) && (k==n) && (n>0);
*/
void loopy_420(int j, int k, int n) {
  
  
  
  
  while (j<n && n>0) {
    j++;k--;
  }
  {;
//@ assert((k == 0));
}

  return;
}