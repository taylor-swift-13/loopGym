// Source: data/benchmarks/code2inv/124.c

void loopy_241(int x, int y) {
  
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
  
if ( (i == j) )
{;
//@ assert( (y == 0) );
}

}