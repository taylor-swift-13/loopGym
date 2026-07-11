// Source: data/benchmarks/code2inv/88.c
extern int unknown(void);

void loopy_325(int x) {
  
  int lock;
  
  int y;
  
  (y = (x + 1));
  (lock = 0);
  
  while ((x != y)) {
    {
      if ( unknown() ) {
        {
        (lock  = 1);
        (x  = y);
        }
      } else {
        {
        (lock  = 0);
        (x  = y);
        (y  = (y + 1));
        }
      }

    }

  }
  
{;
//@ assert( (lock == 1) );
}

}