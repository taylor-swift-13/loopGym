// Source: data/benchmarks/code2inv/78.c
extern int unknown(void);

/*@
  requires (x >= 0);
  requires (y >= 0);
  requires (x >= y);
*/
void loopy_314(int x, int y) {
  
  int i;
  
  
  
  (i = 0);
  
  
  
  
  while (unknown()) {
    if ( (i < y) )
    {
    (i  = (i + 1));
    }

  }
  
if ( (i < y) )
{;
//@ assert( (0 <= i) );
}

}