// Source: data/benchmarks/code2inv/110.c

void loopy_226(int n) {
  
  int i;
  
  int sn;
  
  (sn = 0);
  (i = 1);
  
  while ((i <= n)) {
    {
    (i  = (i + 1));
    (sn  = (sn + 1));
    }

  }
  
if ( (sn != n) )
{;
//@ assert( (sn == 0) );
}

}