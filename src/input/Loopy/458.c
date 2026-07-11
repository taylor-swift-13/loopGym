// Source: data/benchmarks/sv-benchmarks/loops-crafted-1/vnew2.c
extern unsigned int unknown_uint(void);

int SIZE = 20000001;

/*@
  requires n <= SIZE;
*/
void loopy_458(unsigned int n, unsigned int k, unsigned int j) {
  unsigned int i;
  
  i = j = k = 0;
  while( i < n ) {
    i = i + 3;
    j = j+3;
    k = k+3;
  }
  if(n>0)
	  {;
//@ assert( i==j && j==k && (i%(SIZE+2)) );
}

  return;
}
