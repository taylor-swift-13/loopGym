// Source: data/benchmarks/sv-benchmarks/loops-crafted-1/loopv1.c
extern int unknown_int(void);

int SIZE = 50000001;

/*@
  requires n <= SIZE;
*/
void loopy_441(int n) {
  int i, j;
  
  i = 0; j=0;
  while(i<n){ 
 
    if(unknown_int())	  
      i = i + 6; 
    else
     i = i + 3;    
  }
  {;
//@ assert( (i%3) == 0 );
}

  return;
}