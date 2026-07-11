// Source: data/benchmarks/code2inv/81.c
extern int unknown(void);

/*@
  requires (x >= 0);
  requires (y >= 0);
  requires (x >= y);
*/
void loopy_318(int x, int y, int z1, int z2, int z3) {
  
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