// Source: data/benchmarks/code2inv/120.c

void loopy_237(void) {
  
  int i;
  int sn;
  
  (sn = 0);
  (i = 1);
  
  while ((i <= 8)) {
    {
    (i  = (i + 1));
    (sn  = (sn + 1));
    }

  }
  
if ( (sn != 8) )
{;
//@ assert( (sn == 0) );
}

}