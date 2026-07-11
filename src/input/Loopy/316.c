// Source: data/benchmarks/code2inv/8.c
extern int unknown(void);

/*@
  requires (x >= 0);
  requires (x <= 10);
  requires (y <= 10);
  requires (y >= 0);
*/
void loopy_316(int x, int y) {
  
  
  
  
  
  
  
  
  
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