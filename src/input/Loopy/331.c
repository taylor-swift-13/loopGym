// Source: data/benchmarks/code2inv/93.c
extern int unknown(void);

/*@
  requires (n >= 0);
*/
void loopy_331(int n) {
  
  int i;
  
  int x;
  int y;
  
  
  (i = 0);
  (x = 0);
  (y = 0);
  
  while ((i < n)) {
    {
    (i  = (i + 1));
      if ( unknown() ) {
        {
        (x  = (x + 1));
        (y  = (y + 2));
        }
      } else {
        {
        (x  = (x + 2));
        (y  = (y + 1));
        }
      }

    }

  }
  
{;
//@ assert( ((3 * n) == (x + y)) );
}

}