// Source: data/benchmarks/code2inv/121.c

void loopy_238(void) {
  
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
  
if ( (sn != 0) )
{;
//@ assert( (sn == 8) );
}

}