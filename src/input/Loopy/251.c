// Source: data/benchmarks/code2inv/133.c

/*@
  requires (n >= 0);
*/
void loopy_251(int n) {
  
  
  int x;
  
  (x = 0);
  
  
  while ((x < n)) {
    {
    (x  = (x + 1));
    }

  }
  
{;
//@ assert( (x == n) );
}

}