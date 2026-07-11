// Source: data/benchmarks/code2inv/14.c
extern int unknown(void);

/*@
  requires (x >= 0);
  requires (x <= 2);
  requires (y <= 2);
  requires (y >= 0);
*/
void loopy_252(int x, int y, int z1, int z2, int z3) {
  
  
  
  
  
  
  
  
  
  
  
  
  while (unknown()) {
    {
    (x  = (x + 2));
    (y  = (y + 2));
    }

  }
  
if ( (y == 0) )
{;
//@ assert( (x != 4) );
}

}