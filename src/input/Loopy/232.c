// Source: data/benchmarks/code2inv/116.c
extern int unknown(void);

void loopy_232(int v1, int v2, int v3) {
  
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
  
if ( (sn != x) )
{;
//@ assert( (sn == -1) );
}

}