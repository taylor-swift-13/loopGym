// Source: data/benchmarks/code2inv/58.c
extern int unknown(void);

/*@
  requires (n > 0);
*/
void loopy_296(int n, int v1, int v2, int v3) {
  
  int c;
  
  
  
  
  
  (c = 0);
  
  
  while (unknown()) {
    {
      if ( unknown() ) {
        if ( (c != n) )
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
//@ assert( (c >= 0) );
}

}