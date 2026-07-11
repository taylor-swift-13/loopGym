// Source: data/benchmarks/code2inv/87.c
extern int unknown(void);

void loopy_324(int y) {
  
  int lock;
  int x;
  
  
  (x = y);
  (lock = 1);
  
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