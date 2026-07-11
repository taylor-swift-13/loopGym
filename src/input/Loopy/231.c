// Source: data/benchmarks/code2inv/115.c
extern int unknown(void);

void loopy_231(void) {
  
  int sn;
  int x;
  
  (sn = 0);
  (x = 0);
  
  while (unknown()) {
    {
    (x  = (x + 1));
    (sn  = (sn + 1));
    }

  }
  
if ( (sn != -1) )
{;
//@ assert( (sn == x) );
}

}