// Source: data/benchmarks/sv-benchmarks/loop-zilu/benchmark18_conjunctive.c
extern int unknown_int(void);
/*@
  requires (i==0) && (k==0) && (n>0);
*/
void loopy_405(int i, int k, int n) {
  
  
  
  
  while (i < n) {
    i++;k++;
  }
  {;
//@ assert((i == k) && (k == n));
}

  return;
}