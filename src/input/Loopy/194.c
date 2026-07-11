// Source: data/benchmarks/accelerating_invariant_generation/invgen/gulwani_cegar2.c

int __BLAST_NONDET;
void loopy_194(int n) {
  int x, m;

  x = 0;
  m = 0;
  while( x < n ) {
    if(__BLAST_NONDET)
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