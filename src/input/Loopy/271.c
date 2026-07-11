// Source: data/benchmarks/code2inv/35.c
extern int unknown(void);

void loopy_271(void) {
  
  int c;
  
  (c = 0);
  
  while (unknown()) {
    {
      if ( unknown() ) {
        if ( (c != 40) )
        {
        (c  = (c + 1));
        }
      } else {
        if ( (c == 40) )
        {
        (c  = 1);
        }
      }

    }

  }
  
if ( (c != 40) )
{;
//@ assert( (c >= 0) );
}

}