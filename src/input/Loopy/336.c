// Source: data/benchmarks/code2inv/98.c

void loopy_336(int x) {
  
  int i;
  int j;
  
  int y;
  
  (j = 0);
  (i = 0);
  (y = 2);
  
  while ((i <= x)) {
    {
    (i  = (i + 1));
    (j  = (j + y));
    }

  }
  
if ( (i != j) )
{;
//@ assert( (y != 1) );
}

}