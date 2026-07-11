// Source: data/benchmarks/sv-benchmarks/loop-zilu/benchmark19_conjunctive.c
extern int unknown_int(void);
/*@
  requires (j==n) && (k==n) && (n>0);
*/
void loopy_406(int j, int k, int n) {
  
  
  
  
  while (j>0 && n>0) {
    j--;k--;
  }
  {;
//@ assert((k == 0));
}

  return;
}