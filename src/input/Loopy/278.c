// Source: data/benchmarks/code2inv/41.c
extern int unknown(void);

/*@
  requires (n > 0);
*/
void loopy_278(int n) {
  
  int c;
  
  
  (c = 0);
  
  
  while (unknown()) {
    {
      if ( unknown() ) {
        if ( (c > n) )
        {
        (c  = (c + 1));
        }
      } else {
        if ( (c == n) )
        {
        (c  = 1);
        }
      }

    }

  }
  
if ( (c != n) )
{;
//@ assert( (c <= n) );
}

}