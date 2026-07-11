// Source: data/benchmarks/code2inv/11.c
extern int unknown(void);

/*@
  requires (x >= 0);
  requires (x <= 10);
  requires (y <= 10);
  requires (y >= 0);
*/
void loopy_225(int x, int y, int z1, int z2, int z3) {
  
  
  
  
  
  
  
  
  
  
  
  
  while (unknown()) {
    {
    (x  = (x + 10));
    (y  = (y + 10));
    }

  }
  
if ( (x == 20) )
{;
//@ assert( (y != 0) );
}

}