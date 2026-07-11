// Source: data/benchmarks/accelerating_invariant_generation/invgen/gulwani_cegar1.c

int __BLAST_NONDET;
/*@
  requires 0 <= x;
  requires x <= 2;
  requires 0 <= y;
  requires y <= 2;
*/
void loopy_193(int x, int y) {
  

    
    
  while( __BLAST_NONDET ) {
	x+=2;
	y+=2;
  }
  if( y >= 0 ) 
    if( y <= 0 ) 
      if( 4 <= x ) 
	{;
//@ assert( x < 4 );
}

}