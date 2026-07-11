// Source: data/benchmarks/code2inv/99.c

/*@
  requires (n >= 0);
*/
void loopy_337(int n) {
  
  
  int x;
  int y;
  
  
  (x = n);
  (y = 0);
  
  while ((x > 0)) {
    {
    (y  = (y + 1));
    (x  = (x - 1));
    }

  }
  
{;
//@ assert( (n == (x + y)) );
}

}