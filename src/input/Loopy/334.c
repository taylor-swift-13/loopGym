// Source: data/benchmarks/code2inv/96.c

void loopy_334(int x) {
  
  int i;
  int j;
  
  int y;
  
  (j = 0);
  (i = 0);
  (y = 1);
  
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