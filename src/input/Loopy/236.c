// Source: data/benchmarks/code2inv/12.c
extern int unknown(void);

/*@
  requires (x >= 0);
  requires (x <= 10);
  requires (y <= 10);
  requires (y >= 0);
*/
void loopy_236(int x, int y, int z1, int z2, int z3) {
  
  
  
  
  
  
  
  
  
  
  
  
  while (unknown()) {
    {
    (x  = (x + 10));
    (y  = (y + 10));
    }

  }
  
if ( (y == 0) )
{;
//@ assert( (x != 20) );
}

}