// Source: data/benchmarks/sv-benchmarks/loops-crafted-1/sumt3.c
extern unsigned int unknown_uint(void);

int SIZE = 20000001;

/*@
  requires n <= SIZE;
*/
void loopy_451(unsigned int n) {
  unsigned int i, k, j, l=0;
  
  i = 0;
  j = 0;
  k = 0;
  l=0;
  while( l < n ) {
	
	  if(!(l%3))
	    i = i + 1;
	  else if(!(l%2)) 
		  j = j+1;
	  else 
	    k = k+1;
    l = l+1;
  }
  {;
//@ assert((i+j+k) == l);
}

  return;
}
