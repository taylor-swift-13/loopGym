// Source: data/benchmarks/accelerating_invariant_generation/invgen/simple.c

/*@
  requires n > 0;
*/
void loopy_200(int n) {
  int x=0;
  
  
  
  while( x < n ){
    x++;
  }
  {;
//@ assert( x<=n );
}

}