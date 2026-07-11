// Source: data/benchmarks/code2inv/77.c
extern int unknown(void);

/*@
  requires (x >= 0);
  requires (y >= 0);
  requires (x >= y);
*/
void loopy_313(int x, int y) {
  
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
//@ assert( (i < x) );
}

}