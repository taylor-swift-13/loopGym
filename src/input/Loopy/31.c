// Source: data/benchmarks/LinearArbitrary-SeaHorn/invgen/gulwani_cegar1.c
extern int unknown(void);

extern int unknown();

/*@
  requires 0 <= x;
  requires x <= 2;
  requires 0 <= y;
  requires y <= 2;
*/
void loopy_31(int x, int y) {
  
  

    
    

  if (x >= 0 && x <= 2 && y >= 0 && y <= 2) {
  while( unknown() ) {
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
}