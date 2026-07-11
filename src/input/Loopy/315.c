// Source: data/benchmarks/code2inv/79.c
extern int unknown(void);

/*@
  requires (x >= 0);
  requires (y >= 0);
  requires (x >= y);
*/
void loopy_315(int x, int y) {
  
  int i;
  
  
  
  (i = 0);
  
  
  
  
  while (unknown()) {
    if ( (i < y) )
    {
    (i  = (i + 1));
    }

  }
  
if ( (i >= x) )
if ( (0 > i) )
{;
//@ assert( (i >= y) );
}

}