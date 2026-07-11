// Source: data/benchmarks/accelerating_invariant_generation/invgen/up-nested.c

int NONDET;

/*@
  requires j<=n;
*/
void loopy_203(int n, int j) {
  int i, k;

  i = 0;
  k = 0;

  
  while ( j <= n ) {
    
    if (!(i >= 0)) return;
    
    j++;
  }
  {;
//@ assert( i>= 0);
}

}