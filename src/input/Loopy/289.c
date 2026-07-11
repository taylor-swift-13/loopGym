// Source: data/benchmarks/code2inv/51.c
extern int unknown(void);

void loopy_289(void) {
  
  int c;
  
  (c = 0);
  
  while (unknown()) {
    {
      if ( unknown() ) {
        if ( (c != 4) )
        {
        (c  = (c + 1));
        }
      } else {
        if ( (c == 4) )
        {
        (c  = 1);
        }
      }

    }

  }
  
if ( (c != 4) )
{;
//@ assert( (c <= 4) );
}

}