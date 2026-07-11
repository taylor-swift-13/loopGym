// Source: data/benchmarks/code2inv/74.c
extern int unknown(void);

/*@
  requires (y >= 0);
  requires (y >= 127);
*/
void loopy_311(int x1, int x2, int x3, int y) {
  
  int c;
  
  
  
  
  int z;
  
  (c = 0);
  
  
  (z = (36 * y));
  
  while (unknown()) {
    if ( (c < 36) )
    {
    (z  = (z + 1));
    (c  = (c + 1));
    }

  }
  
if ( (c < 36) )
{;
//@ assert( (z >= 0) );
}

}