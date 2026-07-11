// Source: data/benchmarks/code2inv/10.c
extern int unknown(void);

/*@
  requires (x >= 0);
  requires (x <= 2);
  requires (y <= 2);
  requires (y >= 0);
*/
void loopy_215(int x, int y) {
  
  
  
  
  
  
  
  
  
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