// Source: data/benchmarks/sv-benchmarks/loops-crafted-1/iftelse.c
extern unsigned int unknown_uint(void);

int SIZE = 20000001;

/*@
  requires n <= SIZE;
*/
void loopy_440(unsigned int n, unsigned int k, unsigned int j) {
  unsigned int i;
  
  i = j = k = 0;
  while( i < n ) {
    i = i + 3;
    if(i%2)
	    j = j+3;
    else
	    k = k+3;
    if(n>0)
	  {;
//@ assert( (i/2<=j) );
}

  }
  return;
}
