// Source: data/benchmarks/LinearArbitrary-SeaHorn/invgen/simple_if.c

void loopy_40(int n, int m) {
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