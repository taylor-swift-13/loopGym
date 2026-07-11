// Source: data/benchmarks/sv-benchmarks/loops-crafted-1/sumt6.c
extern int unknown_int(void);

int SIZE = 20000001;

/*@
  requires n <= SIZE;
*/
void loopy_454(unsigned int n) {
  unsigned int i=0, k=0, j=0, l=0;
  unsigned int v2=0, v3=0, v4=0;
  
  while( l < n ) {
	
	  if(!(l%6))
	    v2 = v2 + 1;
	  else if(!(l%5))
	    v3 = v3 + 1;
	  else if(!(l%4))
	    v4 = v4 + 1;
	  else if(!(l%3))
	    i = i + 1;
	  else if(!(l%2)) 
		  j = j+1;
	  else 
	    k = k+1;
    l = l+1;
  }
  {;
//@ assert((i+j+k+v4+v3+v2) == l);
}

  return;
}
