// Source: data/benchmarks/code2inv/95.c

void loopy_333(int x) {
  
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
  
if ( (y == 1) )
{;
//@ assert( (i == j) );
}

}