// Source: data/benchmarks/code2inv/100.c

/*@
  requires (n >= 0);
*/
void loopy_216(int n) {
  
  
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
//@ assert( (y == n) );
}

}