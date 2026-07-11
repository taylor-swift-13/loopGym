// Source: data/benchmarks/accelerating_invariant_generation/invgen/simple_if.c

void loopy_201(int n, int m) {
  
  int i = 1;
   
  while( i < n ) {
    if( m > 0 ) {
      i = 2*i;
    } else {
      i = 3*i;
    }
    
  }
  {;
//@ assert(i > 0 );
}

}