// Source: data/benchmarks/code2inv/49.c
extern int unknown(void);

/*@
  requires (n > 0);
*/
void loopy_286(int n) {
  
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
  
if ( (n <= -1) )
{;
//@ assert( (c != n) );
}

}