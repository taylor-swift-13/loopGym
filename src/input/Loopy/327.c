// Source: data/benchmarks/code2inv/9.c
extern int unknown(void);

/*@
  requires (x >= 0);
  requires (x <= 2);
  requires (y <= 2);
  requires (y >= 0);
*/
void loopy_327(int x, int y) {
  
  
  
  
  
  
  
  
  
  while (unknown()) {
    {
    (x  = (x + 2));
    (y  = (y + 2));
    }

  }
  
if ( (x == 4) )
{;
//@ assert( (y != 0) );
}

}