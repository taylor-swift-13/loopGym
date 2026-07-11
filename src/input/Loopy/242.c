// Source: data/benchmarks/code2inv/125.c

void loopy_242(int x, int y) {
  
  int i;
  int j;
  
  
  
  (i = x);
  (j = y);
  
  while ((x != 0)) {
    {
    (x  = (x - 1));
    (y  = (y - 1));
    }

  }
  
if ( (y != 0) )
{;
//@ assert( (i != j) );
}

}