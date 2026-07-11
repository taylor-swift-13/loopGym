// Source: data/benchmarks/code2inv/94.c

/*@
  requires (k >= 0);
  requires (n >= 0);
*/
void loopy_332(int k, int n) {
  
  int i;
  int j;
  
  
  
  
  
  (i = 0);
  (j = 0);
  
  while ((i <= n)) {
    {
    (i  = (i + 1));
    (j  = (j + i));
    }

  }
  
{;
//@ assert( ((i + (j + k)) > (2 * n)) );
}

}