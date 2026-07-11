// Source: data/benchmarks/code2inv/2.c

void loopy_258(void) {
  
  int x;
  int y;
  
  (x = 1);
  (y = 0);
  
  while ((y < 1000)) {
    {
    (x  = (x + y));
    (y  = (y + 1));
    }

  }
  
{;
//@ assert( (x >= y) );
}

}