// Source: data/benchmarks/accelerating_invariant_generation/cav/07.c

int unknown1(){
    int x; return x;
}

int unknown2();
int unknown3();
int unknown4();

/*@
  requires n >= 0;
*/
void loopy_150(int n)
{
  
  int i=0, j=0;
  

  while(i<n) {
    i++;
    j++;
  }	
  if(j >= n+1)
  { goto ERROR;
    { ERROR: {; 
//@ assert(\false);
}
}
  }
}
