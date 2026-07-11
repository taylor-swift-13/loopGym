// Source: data/benchmarks/LinearArbitrary-SeaHorn/invgen/gulwani_cegar2.c
extern int unknown(void);

extern int unknown();

void loopy_32(int n) {
  int x, m;
  x = 0;
  m = 0;
  while( x < n ) {
    if(unknown())
	m = x;
	x++;
  }
  if( n > 0 )
    {
      {;
//@ assert( 0<=m);
}

      {;
//@ assert(m<n);
}

    }
}